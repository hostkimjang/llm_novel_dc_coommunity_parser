"""Presented exhaustive neutral-review accounting for the P0 40-input batch.

This pure component converts the predecessor's unreviewed inventory into forty
input-level review units, seals a pseudonymous roster and exactly-one
assignments before review, and records one explicit terminal per input.  A
JUDGED terminal carries the complete caller-presented neutral gold-span set for
the payload; UNAVAILABLE and UNJUDGED carry null gold and arithmetic fields.

All reviewer identities, assignments, timestamps, and judgments are presented
data.  Structural completeness is not human factuality, semantic gold, actual
source evidence, a quality metric, or authority to touch route/packet/ledger,
publication, or the central Slang DB.
"""

from __future__ import annotations

import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping, Sequence

from . import p0_presented_batch_exact_accounting_v1_contract as batch_contract
from . import p0_presented_batch_exact_accounting_v1_parent_validator as batch_parent


REVIEWER_ROW_SCHEMA = "p0_presented_neutral_reviewer_row_v1"
REVIEW_UNIT_ROW_SCHEMA = "p0_presented_neutral_input_review_unit_v1"
ASSIGNMENT_ROW_SCHEMA = "p0_presented_neutral_review_assignment_v1"
REVIEW_PRECOMMIT_SCHEMA = "p0_presented_neutral_review_precommit_v1"
GOLD_SPAN_SCHEMA = "p0_presented_neutral_gold_span_v1"
OBSERVATION_ADJUDICATION_SCHEMA = "p0_presented_neutral_observation_adjudication_v1"
REVIEW_RESULT_ROW_SCHEMA = "p0_presented_neutral_input_review_result_v1"
REVIEW_RECEIPT_SCHEMA = "p0_presented_neutral_review_accounting_receipt_v1"
COMPONENT_MANIFEST_SCHEMA = "p0_presented_neutral_review_component_manifest_v1"

COMPONENT_VERSION = "presented-neutral-review-accounting-v1"
RECORD_ORIGIN = "ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
EXPECTED_INPUT_COUNT = 40
MAX_REVIEWERS = 16
# A gold span consumes one complete, non-empty relation line.  The shortest
# accepted relation line is 12 characters and adjacent lines consume one LF,
# so the explicit 64 KiB review-document domain can contain at most 5,041 such
# lines.  This remains independent of the parser's 64-emission fail-close cap.
# Strict UTF-8 payloads outside the review-document domain must use an explicit
# UNAVAILABLE terminal instead of claiming a complete JUDGED span set.
MAX_GOLD_SPANS_PER_INPUT = 5041
MAX_DOCUMENT_CHARS = 64 * 1024
MIN_RELATION_LINE_CHARS = 12
MAX_METADATA_CHARS = 512
MAX_SURFACE_CHARS = 512
MAX_DEFINITION_CHARS = 4096
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_JSONL_BYTES = 32 * 1024 * 1024
ANNOTATION_STATUSES = ("JUDGED", "UNAVAILABLE", "UNJUDGED")
OBSERVATION_VERDICTS = ("CONFIRMED", "SPURIOUS")
RELATION_KIND = "PRESENTED_EXPLICIT_DEFINITION_STATEMENT"
SAMPLING_UNIT = "SELECTED_INPUT_LINEAGE"
METRIC_STATUS = "NOT_ESTIMABLE_PRESENTED_REVIEW_ONLY"
GATE_STATUS = "NO_GO_PRESENTED_REVIEW_ACCOUNTING_ONLY"

_STATUS_REASON = {
    "JUDGED": "PRESENTED_FULL_PAYLOAD_REVIEW_RECORDED",
    "UNAVAILABLE": "PRESENTED_REVIEW_UNAVAILABLE",
    "UNJUDGED": "PRESENTED_REVIEW_NOT_COMPLETED",
}
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_RELATION_RE = re.compile(
    r"^'(?P<surface>[^'\n]{1,512})'(?:은|는) "
    r"(?P<presented_definition>.+?)(?:을|를) 뜻한다\.$"
)
_FORBIDDEN_CATEGORIES = frozenset(("Cc", "Cf", "Cs", "Zl", "Zp"))
_FORBIDDEN_SEMANTIC_FIELDS = frozenset(
    {
        "target_work_id",
        "target_sense_id",
        "alias_relation",
        "truth_label",
        "work_id",
        "sense_id",
        "retrieval_query",
        "route_class",
        "publication_decision",
        "credit_count",
        "free_form_note",
        "reviewer_name",
        "reviewer_email",
    }
)

_FALSE_AUTHORITY_FIELDS = (
    "reviewer_identity_authority_verified",
    "reviewer_assignment_factuality_verified",
    "reviewer_independence_verified",
    "reviewer_blinding_verified",
    "human_judgment_factuality_verified",
    "gold_span_semantic_factuality_verified",
    "gold_span_completeness_factuality_verified",
    "trusted_time_verified",
    "code_identity_verified",
    "dependency_closure_verified",
    "process_isolation_verified",
    "runtime_execution_authority_verified",
    "route_packet_ledger_credit_verified",
    "actual_source_evidence_verified",
    "actual_authority_granted",
    "exhaustive_human_review_verified",
    "p0_phase_exit",
    "production_approval",
    "full_scan_approval",
)

_REVIEWER_FIELDS = frozenset(
    {
        "schema_version",
        "reviewer_sequence",
        "reviewer_id",
        "identity_commitment_sha256",
        "independence_group_id",
        "reviewer_row_sha256",
    }
)
_EMITTED_SUBJECT_FIELDS = frozenset(
    {
        "contextual_observation_unit_sha256",
        "schema_version",
        "observation_sequence",
        "line_number",
        "relation_kind",
        "character_span_start",
        "character_span_end",
        "utf8_byte_span_start",
        "utf8_byte_span_end",
        "evidence_text",
        "evidence_utf8_sha256",
        "surface_text",
        "surface_utf8_sha256",
        "presented_definition_text",
        "presented_definition_utf8_sha256",
        "observation_sha256",
    }
)
_UNIT_FIELDS = frozenset(
    {
        "schema_version",
        "review_unit_sequence",
        "input_sequence",
        "frame_candidate_id",
        "registry_record_id",
        "selected_input_sha256",
        "bridge_row_sha256",
        "payload_base64",
        "payload_bytes",
        "payload_sha256",
        "result_row_sha256",
        "parser_terminal_disposition",
        "full_payload_missed_span_unit_sha256",
        "emitted_observation_subjects",
        "emitted_observation_subjects_sha256",
        "emitted_observation_count",
        "input_review_unit_sha256",
    }
)
_ASSIGNMENT_FIELDS = frozenset(
    {
        "schema_version",
        "assignment_sequence",
        "input_review_unit_sha256",
        "input_sequence",
        "reviewer_id",
        "reviewer_identity_commitment_sha256",
        "independence_group_id",
        "semantic_target_blind_required",
        "assignment_row_sha256",
    }
)
_PRECOMMIT_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "component_version",
        "upstream_component_manifest_sha256",
        "upstream_sampling_plan_raw_sha256",
        "upstream_bridge_inventory_raw_sha256",
        "upstream_batch_precommit_raw_sha256",
        "upstream_results_raw_sha256",
        "upstream_batch_receipt_raw_sha256",
        "upstream_unreviewed_inventory_raw_sha256",
        "upstream_unreviewed_inventory_artifact_sha256",
        "review_guideline_sha256",
        "reviewer_roster_raw_sha256",
        "reviewer_roster_row_count",
        "review_unit_inventory_raw_sha256",
        "review_unit_inventory_row_count",
        "review_unit_inventory_sha256",
        "assignment_inventory_raw_sha256",
        "assignment_inventory_row_count",
        "assignment_inventory_sha256",
        "annotation_statuses",
        "observation_verdicts",
        "expected_input_count",
        "max_gold_spans_per_input",
        "assignment_sealed_at",
        "review_precommitted_at",
        "presented_policy_only",
        *_FALSE_AUTHORITY_FIELDS,
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)
_GOLD_FIELDS = frozenset(
    {
        "schema_version",
        "gold_span_sequence",
        "line_number",
        "relation_kind",
        "character_span_start",
        "character_span_end",
        "utf8_byte_span_start",
        "utf8_byte_span_end",
        "evidence_text",
        "evidence_utf8_sha256",
        "surface_text",
        "surface_utf8_sha256",
        "presented_definition_text",
        "presented_definition_utf8_sha256",
        "payload_sha256",
        "gold_span_sha256",
    }
)
_ADJUDICATION_FIELDS = frozenset(
    {
        "schema_version",
        "adjudication_sequence",
        "contextual_observation_unit_sha256",
        "observation_sha256",
        "verdict",
        "matched_gold_span_sha256",
        "adjudication_sha256",
    }
)
_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "result_sequence",
        "input_review_unit_sha256",
        "input_sequence",
        "frame_candidate_id",
        "registry_record_id",
        "payload_sha256",
        "result_row_sha256",
        "full_payload_missed_span_unit_sha256",
        "assignment_row_sha256",
        "assigned_reviewer_id",
        "assigned_reviewer_identity_commitment_sha256",
        "annotation_status",
        "terminal_reason_code",
        "reviewed_at",
        "full_payload_review_complete_presented",
        "observation_adjudications",
        "observation_adjudications_sha256",
        "presented_gold_spans",
        "presented_gold_spans_sha256",
        "gold_span_count",
        "confirmed_emitted_count",
        "spurious_emitted_count",
        "missed_gold_span_count",
        "review_result_row_sha256",
    }
)
_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "record_origin",
        "component_version",
        "review_precommit_raw_sha256",
        "review_precommit_artifact_sha256",
        "review_unit_inventory_raw_sha256",
        "assignment_inventory_raw_sha256",
        "review_results_raw_sha256",
        "review_results_row_count",
        "review_results_inventory_sha256",
        "review_results_sealed_at",
        "receipt_sealed_at",
        "selected_input_itt_denominator",
        "presented_terminal_input_count",
        "presented_missing_terminal_count",
        "presented_duplicate_terminal_count",
        "presented_extra_terminal_count",
        "presented_reordered_terminal_count",
        "annotation_status_counts",
        "presented_unjudged_input_count",
        "presented_unavailable_input_count",
        "presented_judged_input_count",
        "presented_terminal_review_accounting_exhaustive",
        "presented_all_full_payload_inputs_judged",
        "judged_subset_presented_gold_span_set_accounting_verified",
        "contextual_review_denominator",
        "full_payload_review_denominator",
        "judged_subset_emitted_observation_denominator",
        "judged_subset_gold_span_denominator",
        "all_input_emitted_observation_denominator",
        "all_input_gold_span_denominator",
        "judged_subset_presented_gold_span_count",
        "judged_subset_confirmed_emitted_count",
        "judged_subset_spurious_emitted_count",
        "judged_subset_missed_gold_span_count",
        "all_input_gold_span_count",
        "all_input_confirmed_emitted_count",
        "all_input_spurious_emitted_count",
        "all_input_missed_gold_span_count",
        "actual_human_review_count",
        "actual_human_unreviewed_input_count",
        "actual_source_credit_count",
        "actual_context_credit_count",
        "metric_status",
        "descriptive_quality_metrics_allowed",
        "inferential_metrics_allowed",
        "complete_case_metrics_allowed",
        "semantic_metrics_allowed",
        "observation_rows_are_sampling_units",
        "sampling_unit",
        *_FALSE_AUTHORITY_FIELDS,
        "gate_status",
        "action_applied",
        "operational_effect",
        "artifact_sha256",
    }
)


class P0PresentedNeutralReviewError(ValueError):
    """The presented neutral-review accounting contract rejected an input."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_file_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def raw_sha256(value: bytes) -> str:
    if type(value) is not bytes:
        raise P0PresentedNeutralReviewError("raw value must be exact bytes")
    return hashlib.sha256(value).hexdigest()


def with_self_hash(value: Mapping[str, Any], field: str = "artifact_sha256") -> dict[str, Any]:
    material = dict(value)
    material.pop(field, None)
    return {**material, field: canonical_sha256(material)}


def _constant(value: str) -> None:
    raise P0PresentedNeutralReviewError(f"non-finite JSON number forbidden: {value}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise P0PresentedNeutralReviewError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _object(raw: bytes, label: str, maximum: int = MAX_JSON_BYTES) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > maximum:
        raise P0PresentedNeutralReviewError(f"{label} byte length invalid")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise P0PresentedNeutralReviewError(f"{label} BOM/CR forbidden")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise P0PresentedNeutralReviewError(f"{label} UTF-8 invalid") from exc
    if unicodedata.normalize("NFC", text) != text:
        raise P0PresentedNeutralReviewError(f"{label} must be NFC")
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except (json.JSONDecodeError, RecursionError, TypeError, ValueError) as exc:
        raise P0PresentedNeutralReviewError(f"{label} JSON invalid") from exc
    if type(value) is not dict:
        raise P0PresentedNeutralReviewError(f"{label} must be object")
    try:
        expected = canonical_file_bytes(value)
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedNeutralReviewError(f"{label} noncanonical") from exc
    if raw != expected:
        raise P0PresentedNeutralReviewError(f"{label} canonical bytes mismatch")
    return value


def _jsonl(raw: bytes, label: str) -> list[dict[str, Any]]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_JSONL_BYTES:
        raise P0PresentedNeutralReviewError(f"{label} byte length invalid")
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise P0PresentedNeutralReviewError(f"{label} BOM/CR forbidden")
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise P0PresentedNeutralReviewError(f"{label} terminal LF invalid")
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(raw[:-1].split(b"\n"), start=1):
        if not line:
            raise P0PresentedNeutralReviewError(f"{label} blank row {index}")
        rows.append(_object(line + b"\n", f"{label} row {index}"))
    return rows


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise P0PresentedNeutralReviewError(f"{label} exact fields mismatch")
    if _FORBIDDEN_SEMANTIC_FIELDS.intersection(value):
        raise P0PresentedNeutralReviewError(f"{label} semantic/PII field forbidden")
    return value


def _integer(value: Any, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise P0PresentedNeutralReviewError(f"{field} must be exact integer >= {minimum}")
    return value


def _boolean(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise P0PresentedNeutralReviewError(f"{field} must be exact boolean")
    return value


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA_RE.fullmatch(value) is None:
        raise P0PresentedNeutralReviewError(f"{field} must be lowercase SHA-256")
    return value


def _identifier(value: Any, field: str) -> str:
    if type(value) is not str or _ID_RE.fullmatch(value) is None:
        raise P0PresentedNeutralReviewError(f"{field} invalid")
    return value


def _text(value: Any, field: str, *, maximum: int = MAX_METADATA_CHARS) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > maximum
        or value != value.strip()
        or unicodedata.normalize("NFC", value) != value
        or any(unicodedata.category(char) in _FORBIDDEN_CATEGORIES for char in value)
    ):
        raise P0PresentedNeutralReviewError(f"{field} invalid canonical text")
    return value


def _time(value: Any, field: str) -> datetime:
    if type(value) is not str or _TIME_RE.fullmatch(value) is None:
        raise P0PresentedNeutralReviewError(f"{field} timestamp invalid")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise P0PresentedNeutralReviewError(f"{field} timestamp invalid") from exc
    return parsed


def _self(row: Mapping[str, Any], field: str, label: str) -> None:
    material = dict(row)
    presented = material.pop(field, None)
    if _sha(presented, field) != canonical_sha256(material):
        raise P0PresentedNeutralReviewError(f"{label} self-hash mismatch")


def _false_authority(row: Mapping[str, Any], label: str) -> None:
    for field in _FALSE_AUTHORITY_FIELDS:
        if _boolean(row[field], field) is not False:
            raise P0PresentedNeutralReviewError(f"{label} cannot assert {field}")


def build_reviewer_roster_bytes(reviewers: Sequence[Mapping[str, Any]]) -> bytes:
    if type(reviewers) not in (list, tuple) or not 1 <= len(reviewers) <= MAX_REVIEWERS:
        raise P0PresentedNeutralReviewError("reviewer roster size invalid")
    rows: list[dict[str, Any]] = []
    ids: set[str] = set()
    commitments: set[str] = set()
    for index, item in enumerate(reviewers, start=1):
        row = _strict(item, frozenset({"reviewer_id", "identity_commitment_sha256", "independence_group_id"}), f"reviewer input {index}")
        reviewer_id = _identifier(row["reviewer_id"], "reviewer_id")
        commitment = _sha(row["identity_commitment_sha256"], "identity_commitment_sha256")
        group = _identifier(row["independence_group_id"], "independence_group_id")
        if reviewer_id in ids or commitment in commitments:
            raise P0PresentedNeutralReviewError("reviewer identity duplicate")
        ids.add(reviewer_id)
        commitments.add(commitment)
        material = {
            "schema_version": REVIEWER_ROW_SCHEMA,
            "reviewer_sequence": index,
            "reviewer_id": reviewer_id,
            "identity_commitment_sha256": commitment,
            "independence_group_id": group,
        }
        rows.append({**material, "reviewer_row_sha256": canonical_sha256(material)})
    return b"".join(canonical_file_bytes(row) for row in rows)


def _validate_roster(raw: bytes) -> list[dict[str, Any]]:
    rows = _jsonl(raw, "reviewer roster")
    if not 1 <= len(rows) <= MAX_REVIEWERS:
        raise P0PresentedNeutralReviewError("reviewer roster count invalid")
    ids: set[str] = set()
    commitments: set[str] = set()
    for index, value in enumerate(rows, start=1):
        row = _strict(value, _REVIEWER_FIELDS, f"reviewer row {index}")
        if row["schema_version"] != REVIEWER_ROW_SCHEMA or _integer(row["reviewer_sequence"], "reviewer_sequence", 1) != index:
            raise P0PresentedNeutralReviewError("reviewer physical order mismatch")
        rid = _identifier(row["reviewer_id"], "reviewer_id")
        commitment = _sha(row["identity_commitment_sha256"], "identity_commitment_sha256")
        _identifier(row["independence_group_id"], "independence_group_id")
        if rid in ids or commitment in commitments:
            raise P0PresentedNeutralReviewError("reviewer identity duplicate")
        ids.add(rid)
        commitments.add(commitment)
        _self(row, "reviewer_row_sha256", f"reviewer row {index}")
    return rows


def _validated_upstream(
    *,
    sampling_plan_raw: bytes,
    expected_sampling_plan_raw_sha256: str,
    bridge_inventory_raw: bytes,
    batch_precommit_raw: bytes,
    expected_batch_precommit_raw_sha256: str,
    results_raw: bytes,
    batch_receipt_raw: bytes,
    unreviewed_inventory_raw: bytes,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    try:
        batch_parent.validate_batch_bundle_against_raw_inputs(
            sampling_plan_raw=sampling_plan_raw,
            expected_sampling_plan_raw_sha256=expected_sampling_plan_raw_sha256,
            bridge_inventory_raw=bridge_inventory_raw,
            batch_precommit_raw=batch_precommit_raw,
            expected_precommit_raw_sha256=expected_batch_precommit_raw_sha256,
            results_raw=results_raw,
            batch_receipt_raw=batch_receipt_raw,
            unreviewed_inventory_raw=unreviewed_inventory_raw,
        )
    except Exception as exc:
        raise P0PresentedNeutralReviewError("upstream presented batch rejected") from exc
    bridges = _jsonl(bridge_inventory_raw, "upstream bridge")
    results = _jsonl(results_raw, "upstream results")
    inventory = _object(unreviewed_inventory_raw, "upstream unreviewed inventory")
    if len(bridges) != EXPECTED_INPUT_COUNT or len(results) != EXPECTED_INPUT_COUNT:
        raise P0PresentedNeutralReviewError("upstream input count mismatch")
    return bridges, results, inventory


def _derive_review_units(
    bridges: Sequence[Mapping[str, Any]],
    results: Sequence[Mapping[str, Any]],
    inventory: Mapping[str, Any],
) -> list[dict[str, Any]]:
    contextual_by_input: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for item in inventory["contextual_observation_review_units"]:
        contextual_by_input[_integer(item["input_sequence"], "input_sequence", 1)].append(item)
    missed_by_input = {
        _integer(item["input_sequence"], "input_sequence", 1): item
        for item in inventory["full_payload_missed_span_review_units"]
    }
    if len(missed_by_input) != EXPECTED_INPUT_COUNT:
        raise P0PresentedNeutralReviewError("upstream missed-span universe mismatch")
    units: list[dict[str, Any]] = []
    for index, (bridge, result) in enumerate(zip(bridges, results), start=1):
        if bridge["input_sequence"] != index or result["input_sequence"] != index:
            raise P0PresentedNeutralReviewError("upstream physical order mismatch")
        try:
            payload = base64.b64decode(bridge["payload_base64"], validate=True)
        except Exception as exc:
            raise P0PresentedNeutralReviewError("upstream payload base64 invalid") from exc
        if len(payload) != bridge["payload_bytes"] or hashlib.sha256(payload).hexdigest() != bridge["payload_sha256"]:
            raise P0PresentedNeutralReviewError("upstream payload binding mismatch")
        core_observations = [] if result["core_result"] is None else result["core_result"]["observations"]
        subjects: list[dict[str, Any]] = []
        contextual = contextual_by_input.get(index, [])
        if len(contextual) != len(core_observations):
            raise P0PresentedNeutralReviewError("upstream contextual observation count mismatch")
        for unit, observation in zip(contextual, core_observations):
            if unit["observation_sha256"] != observation["observation_sha256"] or unit["observation_sequence"] != observation["observation_sequence"]:
                raise P0PresentedNeutralReviewError("upstream contextual observation identity mismatch")
            subject = {
                "contextual_observation_unit_sha256": unit["contextual_observation_unit_sha256"],
                **{field: observation[field] for field in _EMITTED_SUBJECT_FIELDS if field != "contextual_observation_unit_sha256"},
            }
            _strict(subject, _EMITTED_SUBJECT_FIELDS, "emitted observation subject")
            subjects.append(subject)
        missed = missed_by_input[index]
        identity = {
            "input_sequence": index,
            "frame_candidate_id": bridge["candidate_id"],
            "registry_record_id": bridge["registry_record_id"],
            "selected_input_sha256": bridge["selected_input_sha256"],
            "bridge_row_sha256": bridge["bridge_row_sha256"],
            "payload_base64": bridge["payload_base64"],
            "payload_bytes": bridge["payload_bytes"],
            "payload_sha256": bridge["payload_sha256"],
            "result_row_sha256": result["result_row_sha256"],
            "parser_terminal_disposition": result["terminal_disposition"],
            "full_payload_missed_span_unit_sha256": missed["full_payload_missed_span_unit_sha256"],
            "emitted_observation_subjects": subjects,
            "emitted_observation_subjects_sha256": canonical_sha256(subjects),
            "emitted_observation_count": len(subjects),
        }
        material = {
            "schema_version": REVIEW_UNIT_ROW_SCHEMA,
            "review_unit_sequence": index,
            **identity,
        }
        units.append({**material, "input_review_unit_sha256": canonical_sha256({"domain": "P0_PRESENTED_NEUTRAL_INPUT_REVIEW_UNIT_V1", **material})})
    return units


def build_review_unit_inventory_bytes(
    *,
    sampling_plan_raw: bytes,
    expected_sampling_plan_raw_sha256: str,
    bridge_inventory_raw: bytes,
    batch_precommit_raw: bytes,
    expected_batch_precommit_raw_sha256: str,
    results_raw: bytes,
    batch_receipt_raw: bytes,
    unreviewed_inventory_raw: bytes,
) -> bytes:
    bridges, results, inventory = _validated_upstream(
        sampling_plan_raw=sampling_plan_raw,
        expected_sampling_plan_raw_sha256=expected_sampling_plan_raw_sha256,
        bridge_inventory_raw=bridge_inventory_raw,
        batch_precommit_raw=batch_precommit_raw,
        expected_batch_precommit_raw_sha256=expected_batch_precommit_raw_sha256,
        results_raw=results_raw,
        batch_receipt_raw=batch_receipt_raw,
        unreviewed_inventory_raw=unreviewed_inventory_raw,
    )
    raw = b"".join(canonical_file_bytes(row) for row in _derive_review_units(bridges, results, inventory))
    if len(raw) > MAX_JSONL_BYTES:
        raise P0PresentedNeutralReviewError("review-unit inventory bound exceeded")
    return raw


def _validate_units(raw: bytes) -> list[dict[str, Any]]:
    rows = _jsonl(raw, "review-unit inventory")
    if len(rows) != EXPECTED_INPUT_COUNT:
        raise P0PresentedNeutralReviewError("review-unit count must be 40")
    for index, value in enumerate(rows, start=1):
        row = _strict(value, _UNIT_FIELDS, f"review unit {index}")
        if (
            row["schema_version"] != REVIEW_UNIT_ROW_SCHEMA
            or _integer(row["review_unit_sequence"], "review_unit_sequence", 1) != index
            or _integer(row["input_sequence"], "input_sequence", 1) != index
        ):
            raise P0PresentedNeutralReviewError("review-unit physical order mismatch")
        for field in ("selected_input_sha256", "bridge_row_sha256", "payload_sha256", "result_row_sha256", "full_payload_missed_span_unit_sha256", "emitted_observation_subjects_sha256"):
            _sha(row[field], field)
        _identifier(row["frame_candidate_id"], "frame_candidate_id")
        _identifier(row["registry_record_id"], "registry_record_id")
        if row["frame_candidate_id"] == row["registry_record_id"]:
            raise P0PresentedNeutralReviewError("candidate and registry IDs must remain distinct")
        try:
            payload = base64.b64decode(row["payload_base64"], validate=True)
        except Exception as exc:
            raise P0PresentedNeutralReviewError("review-unit payload invalid") from exc
        if len(payload) != _integer(row["payload_bytes"], "payload_bytes") or hashlib.sha256(payload).hexdigest() != row["payload_sha256"]:
            raise P0PresentedNeutralReviewError("review-unit payload mismatch")
        subjects = row["emitted_observation_subjects"]
        if type(subjects) is not list or len(subjects) != _integer(row["emitted_observation_count"], "emitted_observation_count") or canonical_sha256(subjects) != row["emitted_observation_subjects_sha256"]:
            raise P0PresentedNeutralReviewError("emitted subject inventory mismatch")
        for subject_index, subject_value in enumerate(subjects, start=1):
            subject = _strict(subject_value, _EMITTED_SUBJECT_FIELDS, f"emitted subject {index}:{subject_index}")
            if (
                _integer(subject["observation_sequence"], "observation_sequence", 1) != subject_index
                or _integer(subject["line_number"], "line_number", 1) < 1
            ):
                raise P0PresentedNeutralReviewError("emitted subject order mismatch")
            for field in (
                "contextual_observation_unit_sha256", "observation_sha256",
                "evidence_utf8_sha256", "surface_utf8_sha256",
                "presented_definition_utf8_sha256",
            ):
                _sha(subject[field], field)
        material = dict(row)
        presented = material.pop("input_review_unit_sha256")
        if _sha(presented, "input_review_unit_sha256") != canonical_sha256({"domain": "P0_PRESENTED_NEUTRAL_INPUT_REVIEW_UNIT_V1", **material}):
            raise P0PresentedNeutralReviewError("review-unit self-hash mismatch")
    return rows


def build_assignment_inventory_bytes(
    review_unit_inventory_raw: bytes,
    reviewer_roster_raw: bytes,
    reviewer_ids_by_input: Sequence[str],
) -> bytes:
    units = _validate_units(review_unit_inventory_raw)
    roster = _validate_roster(reviewer_roster_raw)
    if type(reviewer_ids_by_input) not in (list, tuple) or len(reviewer_ids_by_input) != EXPECTED_INPUT_COUNT:
        raise P0PresentedNeutralReviewError("assignment input count must be 40")
    by_id = {row["reviewer_id"]: row for row in roster}
    rows: list[dict[str, Any]] = []
    for index, (unit, reviewer_id) in enumerate(zip(units, reviewer_ids_by_input), start=1):
        reviewer_id = _identifier(reviewer_id, "reviewer_id")
        if reviewer_id not in by_id:
            raise P0PresentedNeutralReviewError("assignment reviewer absent from roster")
        reviewer = by_id[reviewer_id]
        material = {
            "schema_version": ASSIGNMENT_ROW_SCHEMA,
            "assignment_sequence": index,
            "input_review_unit_sha256": unit["input_review_unit_sha256"],
            "input_sequence": index,
            "reviewer_id": reviewer_id,
            "reviewer_identity_commitment_sha256": reviewer["identity_commitment_sha256"],
            "independence_group_id": reviewer["independence_group_id"],
            "semantic_target_blind_required": True,
        }
        rows.append({**material, "assignment_row_sha256": canonical_sha256(material)})
    return b"".join(canonical_file_bytes(row) for row in rows)


def _validate_assignments(raw: bytes, units: Sequence[Mapping[str, Any]], roster: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = _jsonl(raw, "assignment inventory")
    if len(rows) != EXPECTED_INPUT_COUNT:
        raise P0PresentedNeutralReviewError("assignment count must be 40")
    by_id = {row["reviewer_id"]: row for row in roster}
    for index, (value, unit) in enumerate(zip(rows, units), start=1):
        row = _strict(value, _ASSIGNMENT_FIELDS, f"assignment {index}")
        if (
            row["schema_version"] != ASSIGNMENT_ROW_SCHEMA
            or _integer(row["assignment_sequence"], "assignment_sequence", 1) != index
            or _integer(row["input_sequence"], "input_sequence", 1) != index
            or row["input_review_unit_sha256"] != unit["input_review_unit_sha256"]
        ):
            raise P0PresentedNeutralReviewError("assignment physical identity mismatch")
        reviewer_id = _identifier(row["reviewer_id"], "reviewer_id")
        reviewer = by_id.get(reviewer_id)
        if reviewer is None or row["reviewer_identity_commitment_sha256"] != reviewer["identity_commitment_sha256"] or row["independence_group_id"] != reviewer["independence_group_id"]:
            raise P0PresentedNeutralReviewError("assignment reviewer projection mismatch")
        if _boolean(row["semantic_target_blind_required"], "semantic_target_blind_required") is not True:
            raise P0PresentedNeutralReviewError("semantic target blind assignment required")
        _self(row, "assignment_row_sha256", f"assignment {index}")
    return rows


def build_review_precommit_bytes(
    *,
    sampling_plan_raw: bytes,
    expected_sampling_plan_raw_sha256: str,
    bridge_inventory_raw: bytes,
    batch_precommit_raw: bytes,
    expected_batch_precommit_raw_sha256: str,
    results_raw: bytes,
    batch_receipt_raw: bytes,
    unreviewed_inventory_raw: bytes,
    reviewer_roster_raw: bytes,
    review_unit_inventory_raw: bytes,
    assignment_inventory_raw: bytes,
    review_guideline_sha256: str,
    assignment_sealed_at: str,
    review_precommitted_at: str,
) -> bytes:
    upstream_bridges, upstream_results, upstream_inventory = _validated_upstream(
        sampling_plan_raw=sampling_plan_raw,
        expected_sampling_plan_raw_sha256=expected_sampling_plan_raw_sha256,
        bridge_inventory_raw=bridge_inventory_raw,
        batch_precommit_raw=batch_precommit_raw,
        expected_batch_precommit_raw_sha256=expected_batch_precommit_raw_sha256,
        results_raw=results_raw,
        batch_receipt_raw=batch_receipt_raw,
        unreviewed_inventory_raw=unreviewed_inventory_raw,
    )
    roster = _validate_roster(reviewer_roster_raw)
    units = _validate_units(review_unit_inventory_raw)
    assignments = _validate_assignments(assignment_inventory_raw, units, roster)
    derived_units = _derive_review_units(
        upstream_bridges,
        upstream_results,
        upstream_inventory,
    )
    if canonical_bytes(units) != canonical_bytes(derived_units):
        raise P0PresentedNeutralReviewError("review units differ from upstream artifacts")
    assigned = _time(assignment_sealed_at, "assignment_sealed_at")
    precommitted = _time(review_precommitted_at, "review_precommitted_at")
    if assigned <= _time(upstream_inventory["review_inventory_sealed_at"], "review_inventory_sealed_at") or precommitted <= assigned:
        raise P0PresentedNeutralReviewError("review precommit chronology invalid")
    material = {
        "schema_version": REVIEW_PRECOMMIT_SCHEMA,
        "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "upstream_component_manifest_sha256": batch_contract.COMPONENT_MANIFEST_SHA256,
        "upstream_sampling_plan_raw_sha256": raw_sha256(sampling_plan_raw),
        "upstream_bridge_inventory_raw_sha256": raw_sha256(bridge_inventory_raw),
        "upstream_batch_precommit_raw_sha256": raw_sha256(batch_precommit_raw),
        "upstream_results_raw_sha256": raw_sha256(results_raw),
        "upstream_batch_receipt_raw_sha256": raw_sha256(batch_receipt_raw),
        "upstream_unreviewed_inventory_raw_sha256": raw_sha256(unreviewed_inventory_raw),
        "upstream_unreviewed_inventory_artifact_sha256": upstream_inventory["artifact_sha256"],
        "review_guideline_sha256": _sha(review_guideline_sha256, "review_guideline_sha256"),
        "reviewer_roster_raw_sha256": raw_sha256(reviewer_roster_raw),
        "reviewer_roster_row_count": len(roster),
        "review_unit_inventory_raw_sha256": raw_sha256(review_unit_inventory_raw),
        "review_unit_inventory_row_count": EXPECTED_INPUT_COUNT,
        "review_unit_inventory_sha256": canonical_sha256(units),
        "assignment_inventory_raw_sha256": raw_sha256(assignment_inventory_raw),
        "assignment_inventory_row_count": EXPECTED_INPUT_COUNT,
        "assignment_inventory_sha256": canonical_sha256(assignments),
        "annotation_statuses": list(ANNOTATION_STATUSES),
        "observation_verdicts": list(OBSERVATION_VERDICTS),
        "expected_input_count": EXPECTED_INPUT_COUNT,
        "max_gold_spans_per_input": MAX_GOLD_SPANS_PER_INPUT,
        "assignment_sealed_at": assignment_sealed_at,
        "review_precommitted_at": review_precommitted_at,
        "presented_policy_only": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return canonical_file_bytes(with_self_hash(material))


def _validate_precommit(
    raw: bytes,
    *,
    sampling_plan_raw: bytes,
    expected_sampling_plan_raw_sha256: str,
    bridge_inventory_raw: bytes,
    batch_precommit_raw: bytes,
    expected_batch_precommit_raw_sha256: str,
    results_raw: bytes,
    batch_receipt_raw: bytes,
    unreviewed_inventory_raw: bytes,
    roster_raw: bytes,
    units_raw: bytes,
    assignments_raw: bytes,
) -> dict[str, Any]:
    row = _strict(_object(raw, "review precommit"), _PRECOMMIT_FIELDS, "review precommit")
    _false_authority(row, "review precommit")
    expected = build_review_precommit_bytes(
        sampling_plan_raw=sampling_plan_raw,
        expected_sampling_plan_raw_sha256=expected_sampling_plan_raw_sha256,
        bridge_inventory_raw=bridge_inventory_raw,
        batch_precommit_raw=batch_precommit_raw,
        expected_batch_precommit_raw_sha256=expected_batch_precommit_raw_sha256,
        results_raw=results_raw,
        batch_receipt_raw=batch_receipt_raw,
        unreviewed_inventory_raw=unreviewed_inventory_raw,
        reviewer_roster_raw=roster_raw,
        review_unit_inventory_raw=units_raw,
        assignment_inventory_raw=assignments_raw,
        review_guideline_sha256=row["review_guideline_sha256"],
        assignment_sealed_at=row["assignment_sealed_at"],
        review_precommitted_at=row["review_precommitted_at"],
    )
    if raw != expected:
        raise P0PresentedNeutralReviewError("review precommit exact recomputation mismatch")
    return row


def _line_bounds(document: str) -> dict[int, tuple[int, int]]:
    bounds: dict[int, tuple[int, int]] = {}
    start = 0
    for number, line in enumerate(document.split("\n"), start=1):
        end = start + len(line)
        if line:
            bounds[number] = (start, end)
        start = end + 1
    return bounds


def _span_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        row["line_number"],
        row["character_span_start"],
        row["character_span_end"],
        row["utf8_byte_span_start"],
        row["utf8_byte_span_end"],
        row["evidence_text"],
        row["surface_text"],
        row["presented_definition_text"],
        row["relation_kind"],
    )


def _gold_spans(raw_items: Any, unit: Mapping[str, Any]) -> list[dict[str, Any]]:
    if type(raw_items) not in (list, tuple) or len(raw_items) > MAX_GOLD_SPANS_PER_INPUT:
        raise P0PresentedNeutralReviewError("gold span inventory invalid")
    try:
        payload = base64.b64decode(unit["payload_base64"], validate=True)
        document = payload.decode("utf-8", errors="strict")
    except (UnicodeDecodeError, ValueError) as exc:
        raise P0PresentedNeutralReviewError("JUDGED payload must be strict UTF-8") from exc
    if document.startswith("\ufeff") or "\x00" in document or "\r" in document or unicodedata.normalize("NFC", document) != document:
        raise P0PresentedNeutralReviewError("JUDGED payload text is noncanonical")
    if len(document) > MAX_DOCUMENT_CHARS:
        raise P0PresentedNeutralReviewError("JUDGED payload exceeds review-document domain; use UNAVAILABLE")
    bounds = _line_bounds(document)
    rows: list[dict[str, Any]] = []
    previous_end = -1
    for index, raw_item in enumerate(raw_items, start=1):
        item = _strict(raw_item, frozenset({"line_number", "character_span_start", "character_span_end", "utf8_byte_span_start", "utf8_byte_span_end", "evidence_text", "surface_text", "presented_definition_text"}), f"gold input {index}")
        line_number = _integer(item["line_number"], "line_number", 1)
        start = _integer(item["character_span_start"], "character_span_start")
        end = _integer(item["character_span_end"], "character_span_end", 1)
        if line_number not in bounds or bounds[line_number] != (start, end) or start < previous_end:
            raise P0PresentedNeutralReviewError("gold spans must be sorted non-overlapping whole lines")
        evidence = item["evidence_text"]
        if type(evidence) is not str or document[start:end] != evidence:
            raise P0PresentedNeutralReviewError("gold evidence character binding mismatch")
        byte_start = len(document[:start].encode("utf-8"))
        byte_end = len(document[:end].encode("utf-8"))
        if (
            _integer(item["utf8_byte_span_start"], "utf8_byte_span_start") != byte_start
            or _integer(item["utf8_byte_span_end"], "utf8_byte_span_end", 1) != byte_end
        ):
            raise P0PresentedNeutralReviewError("gold evidence UTF-8 byte binding mismatch")
        surface = _text(item["surface_text"], "surface_text", maximum=MAX_SURFACE_CHARS)
        definition = _text(item["presented_definition_text"], "presented_definition_text", maximum=MAX_DEFINITION_CHARS)
        relation = _RELATION_RE.fullmatch(evidence)
        if relation is None or relation.group("surface") != surface or relation.group("presented_definition") != definition:
            raise P0PresentedNeutralReviewError("gold surface/definition grammar binding mismatch")
        material = {
            "schema_version": GOLD_SPAN_SCHEMA,
            "gold_span_sequence": index,
            "line_number": line_number,
            "relation_kind": RELATION_KIND,
            "character_span_start": start,
            "character_span_end": end,
            "utf8_byte_span_start": byte_start,
            "utf8_byte_span_end": byte_end,
            "evidence_text": evidence,
            "evidence_utf8_sha256": hashlib.sha256(evidence.encode("utf-8")).hexdigest(),
            "surface_text": surface,
            "surface_utf8_sha256": hashlib.sha256(surface.encode("utf-8")).hexdigest(),
            "presented_definition_text": definition,
            "presented_definition_utf8_sha256": hashlib.sha256(definition.encode("utf-8")).hexdigest(),
            "payload_sha256": unit["payload_sha256"],
        }
        rows.append({**material, "gold_span_sha256": canonical_sha256({"domain": "P0_PRESENTED_NEUTRAL_GOLD_SPAN_V1", "input_review_unit_sha256": unit["input_review_unit_sha256"], **material})})
        previous_end = end
    if len({_span_key(row) for row in rows}) != len(rows):
        raise P0PresentedNeutralReviewError("duplicate gold span")
    return rows


def _build_result_row(decision: Mapping[str, Any], unit: Mapping[str, Any], assignment: Mapping[str, Any], precommit: Mapping[str, Any]) -> dict[str, Any]:
    decision = _strict(decision, frozenset({"input_sequence", "annotation_status", "terminal_reason_code", "reviewer_id", "reviewed_at", "gold_spans"}), "review decision")
    index = unit["input_sequence"]
    if decision["input_sequence"] != index:
        raise P0PresentedNeutralReviewError("review decision physical order mismatch")
    status = decision["annotation_status"]
    if status not in ANNOTATION_STATUSES or decision["terminal_reason_code"] != _STATUS_REASON[status]:
        raise P0PresentedNeutralReviewError("review terminal status/reason mismatch")
    if status == "UNJUDGED":
        if decision["reviewer_id"] is not None or decision["reviewed_at"] is not None or decision["gold_spans"] is not None:
            raise P0PresentedNeutralReviewError("UNJUDGED review payload must be null")
        gold = adjudications = None
        gold_sha = adjudications_sha = None
        gold_count = confirmed = spurious = missed = None
        reviewed_at = None
        complete = False
    elif status == "UNAVAILABLE":
        if decision["reviewer_id"] != assignment["reviewer_id"] or decision["gold_spans"] is not None:
            raise P0PresentedNeutralReviewError("UNAVAILABLE review payload mismatch")
        reviewed = _time(decision["reviewed_at"], "reviewed_at")
        if reviewed <= _time(precommit["review_precommitted_at"], "review_precommitted_at"):
            raise P0PresentedNeutralReviewError("review must follow precommit")
        gold = adjudications = None
        gold_sha = adjudications_sha = None
        gold_count = confirmed = spurious = missed = None
        reviewed_at = decision["reviewed_at"]
        complete = False
    else:
        if decision["reviewer_id"] != assignment["reviewer_id"]:
            raise P0PresentedNeutralReviewError("JUDGED reviewer mismatch")
        reviewed = _time(decision["reviewed_at"], "reviewed_at")
        if reviewed <= _time(precommit["review_precommitted_at"], "review_precommitted_at"):
            raise P0PresentedNeutralReviewError("review must follow precommit")
        gold = _gold_spans(decision["gold_spans"], unit)
        gold_by_key = {_span_key(row): row for row in gold}
        emitted = unit["emitted_observation_subjects"]
        adjudications = []
        confirmed = 0
        for subject_index, subject in enumerate(emitted, start=1):
            matched = gold_by_key.get(_span_key(subject))
            verdict = "CONFIRMED" if matched is not None else "SPURIOUS"
            confirmed += int(matched is not None)
            material = {
                "schema_version": OBSERVATION_ADJUDICATION_SCHEMA,
                "adjudication_sequence": subject_index,
                "contextual_observation_unit_sha256": subject["contextual_observation_unit_sha256"],
                "observation_sha256": subject["observation_sha256"],
                "verdict": verdict,
                "matched_gold_span_sha256": None if matched is None else matched["gold_span_sha256"],
            }
            adjudications.append({**material, "adjudication_sha256": canonical_sha256(material)})
        gold_keys = set(gold_by_key)
        emitted_keys = {_span_key(subject) for subject in emitted}
        gold_count = len(gold)
        spurious = len(emitted) - confirmed
        missed = len(gold_keys - emitted_keys)
        gold_sha = canonical_sha256(gold)
        adjudications_sha = canonical_sha256(adjudications)
        reviewed_at = decision["reviewed_at"]
        complete = True
    material = {
        "schema_version": REVIEW_RESULT_ROW_SCHEMA,
        "result_sequence": index,
        "input_review_unit_sha256": unit["input_review_unit_sha256"],
        "input_sequence": index,
        "frame_candidate_id": unit["frame_candidate_id"],
        "registry_record_id": unit["registry_record_id"],
        "payload_sha256": unit["payload_sha256"],
        "result_row_sha256": unit["result_row_sha256"],
        "full_payload_missed_span_unit_sha256": unit["full_payload_missed_span_unit_sha256"],
        "assignment_row_sha256": assignment["assignment_row_sha256"],
        "assigned_reviewer_id": assignment["reviewer_id"],
        "assigned_reviewer_identity_commitment_sha256": assignment["reviewer_identity_commitment_sha256"],
        "annotation_status": status,
        "terminal_reason_code": decision["terminal_reason_code"],
        "reviewed_at": reviewed_at,
        "full_payload_review_complete_presented": complete,
        "observation_adjudications": adjudications,
        "observation_adjudications_sha256": adjudications_sha,
        "presented_gold_spans": gold,
        "presented_gold_spans_sha256": gold_sha,
        "gold_span_count": gold_count,
        "confirmed_emitted_count": confirmed,
        "spurious_emitted_count": spurious,
        "missed_gold_span_count": missed,
    }
    return {**material, "review_result_row_sha256": canonical_sha256(material)}


def _receipt_value(
    *,
    precommit_raw: bytes,
    precommit: Mapping[str, Any],
    units_raw: bytes,
    units: Sequence[Mapping[str, Any]],
    assignments_raw: bytes,
    results_raw: bytes,
    result_rows: Sequence[Mapping[str, Any]],
    results_sealed_at: str,
    receipt_sealed_at: str,
) -> dict[str, Any]:
    sealed = _time(results_sealed_at, "review_results_sealed_at")
    receipt_sealed = _time(receipt_sealed_at, "receipt_sealed_at")
    reviewed_times = [_time(row["reviewed_at"], "reviewed_at") for row in result_rows if row["reviewed_at"] is not None]
    if sealed <= _time(precommit["review_precommitted_at"], "review_precommitted_at") or any(value >= sealed for value in reviewed_times) or receipt_sealed <= sealed:
        raise P0PresentedNeutralReviewError("review result/receipt chronology invalid")
    counts = Counter(row["annotation_status"] for row in result_rows)
    all_judged = counts["JUDGED"] == EXPECTED_INPUT_COUNT
    judged_rows = [row for row in result_rows if row["annotation_status"] == "JUDGED"]
    judged_sequences = {row["input_sequence"] for row in judged_rows}
    contextual_denominator = sum(
        _integer(unit["emitted_observation_count"], "emitted_observation_count")
        for unit in units
    )
    judged_emitted_denominator = sum(
        _integer(unit["emitted_observation_count"], "emitted_observation_count")
        for unit in units
        if unit["input_sequence"] in judged_sequences
    )
    totals = {
        "gold": sum(row["gold_span_count"] for row in judged_rows),
        "confirmed": sum(row["confirmed_emitted_count"] for row in judged_rows),
        "spurious": sum(row["spurious_emitted_count"] for row in judged_rows),
        "missed": sum(row["missed_gold_span_count"] for row in judged_rows),
    }
    material = {
        "schema_version": REVIEW_RECEIPT_SCHEMA,
        "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "review_precommit_raw_sha256": raw_sha256(precommit_raw),
        "review_precommit_artifact_sha256": precommit["artifact_sha256"],
        "review_unit_inventory_raw_sha256": raw_sha256(units_raw),
        "assignment_inventory_raw_sha256": raw_sha256(assignments_raw),
        "review_results_raw_sha256": raw_sha256(results_raw),
        "review_results_row_count": EXPECTED_INPUT_COUNT,
        "review_results_inventory_sha256": canonical_sha256(result_rows),
        "review_results_sealed_at": results_sealed_at,
        "receipt_sealed_at": receipt_sealed_at,
        "selected_input_itt_denominator": EXPECTED_INPUT_COUNT,
        "presented_terminal_input_count": EXPECTED_INPUT_COUNT,
        "presented_missing_terminal_count": 0,
        "presented_duplicate_terminal_count": 0,
        "presented_extra_terminal_count": 0,
        "presented_reordered_terminal_count": 0,
        "annotation_status_counts": {status: counts[status] for status in ANNOTATION_STATUSES},
        "presented_unjudged_input_count": counts["UNJUDGED"],
        "presented_unavailable_input_count": counts["UNAVAILABLE"],
        "presented_judged_input_count": counts["JUDGED"],
        "presented_terminal_review_accounting_exhaustive": counts["UNJUDGED"] == 0,
        "presented_all_full_payload_inputs_judged": all_judged,
        "judged_subset_presented_gold_span_set_accounting_verified": bool(judged_rows),
        "contextual_review_denominator": contextual_denominator,
        "full_payload_review_denominator": EXPECTED_INPUT_COUNT,
        "judged_subset_emitted_observation_denominator": judged_emitted_denominator,
        "judged_subset_gold_span_denominator": totals["gold"],
        "all_input_emitted_observation_denominator": contextual_denominator if all_judged else None,
        "all_input_gold_span_denominator": totals["gold"] if all_judged else None,
        "judged_subset_presented_gold_span_count": totals["gold"],
        "judged_subset_confirmed_emitted_count": totals["confirmed"],
        "judged_subset_spurious_emitted_count": totals["spurious"],
        "judged_subset_missed_gold_span_count": totals["missed"],
        "all_input_gold_span_count": totals["gold"] if all_judged else None,
        "all_input_confirmed_emitted_count": totals["confirmed"] if all_judged else None,
        "all_input_spurious_emitted_count": totals["spurious"] if all_judged else None,
        "all_input_missed_gold_span_count": totals["missed"] if all_judged else None,
        "actual_human_review_count": 0,
        "actual_human_unreviewed_input_count": EXPECTED_INPUT_COUNT,
        "actual_source_credit_count": 0,
        "actual_context_credit_count": 0,
        "metric_status": METRIC_STATUS,
        "descriptive_quality_metrics_allowed": False,
        "inferential_metrics_allowed": False,
        "complete_case_metrics_allowed": False,
        "semantic_metrics_allowed": False,
        "observation_rows_are_sampling_units": False,
        "sampling_unit": SAMPLING_UNIT,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
        "gate_status": GATE_STATUS,
        "action_applied": False,
        "operational_effect": OPERATIONAL_EFFECT,
    }
    return with_self_hash(material)


def execute_presented_review(
    *,
    sampling_plan_raw: bytes,
    expected_sampling_plan_raw_sha256: str,
    bridge_inventory_raw: bytes,
    batch_precommit_raw: bytes,
    expected_batch_precommit_raw_sha256: str,
    results_raw: bytes,
    batch_receipt_raw: bytes,
    unreviewed_inventory_raw: bytes,
    reviewer_roster_raw: bytes,
    review_unit_inventory_raw: bytes,
    assignment_inventory_raw: bytes,
    review_precommit_raw: bytes,
    review_decisions: Sequence[Mapping[str, Any]],
    review_results_sealed_at: str,
    receipt_sealed_at: str,
) -> tuple[bytes, bytes]:
    roster = _validate_roster(reviewer_roster_raw)
    units = _validate_units(review_unit_inventory_raw)
    assignments = _validate_assignments(assignment_inventory_raw, units, roster)
    precommit = _validate_precommit(
        review_precommit_raw,
        sampling_plan_raw=sampling_plan_raw,
        expected_sampling_plan_raw_sha256=expected_sampling_plan_raw_sha256,
        bridge_inventory_raw=bridge_inventory_raw,
        batch_precommit_raw=batch_precommit_raw,
        expected_batch_precommit_raw_sha256=expected_batch_precommit_raw_sha256,
        results_raw=results_raw,
        batch_receipt_raw=batch_receipt_raw,
        unreviewed_inventory_raw=unreviewed_inventory_raw,
        roster_raw=reviewer_roster_raw,
        units_raw=review_unit_inventory_raw,
        assignments_raw=assignment_inventory_raw,
    )
    if type(review_decisions) not in (list, tuple) or len(review_decisions) != EXPECTED_INPUT_COUNT:
        raise P0PresentedNeutralReviewError("review decisions must contain exactly 40 rows")
    result_rows = [_build_result_row(decision, unit, assignment, precommit) for decision, unit, assignment in zip(review_decisions, units, assignments)]
    review_results_raw = b"".join(canonical_file_bytes(row) for row in result_rows)
    if len(review_results_raw) > MAX_JSONL_BYTES:
        raise P0PresentedNeutralReviewError("review results bound exceeded")
    receipt = _receipt_value(
        precommit_raw=review_precommit_raw,
        precommit=precommit,
        units_raw=review_unit_inventory_raw,
        units=units,
        assignments_raw=assignment_inventory_raw,
        results_raw=review_results_raw,
        result_rows=result_rows,
        results_sealed_at=review_results_sealed_at,
        receipt_sealed_at=receipt_sealed_at,
    )
    return review_results_raw, canonical_file_bytes(receipt)


def _validate_review_results(raw: bytes, units: Sequence[Mapping[str, Any]], assignments: Sequence[Mapping[str, Any]], precommit: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = _jsonl(raw, "review results")
    if len(rows) != EXPECTED_INPUT_COUNT:
        raise P0PresentedNeutralReviewError("review result count must be 40")
    decisions: list[dict[str, Any]] = []
    for index, (value, unit, assignment) in enumerate(zip(rows, units, assignments), start=1):
        row = _strict(value, _RESULT_FIELDS, f"review result {index}")
        if (
            row["schema_version"] != REVIEW_RESULT_ROW_SCHEMA
            or _integer(row["result_sequence"], "result_sequence", 1) != index
            or _integer(row["input_sequence"], "input_sequence", 1) != index
        ):
            raise P0PresentedNeutralReviewError("review result physical order mismatch")
        exact = {
            "input_review_unit_sha256": unit["input_review_unit_sha256"],
            "frame_candidate_id": unit["frame_candidate_id"],
            "registry_record_id": unit["registry_record_id"],
            "payload_sha256": unit["payload_sha256"],
            "result_row_sha256": unit["result_row_sha256"],
            "full_payload_missed_span_unit_sha256": unit["full_payload_missed_span_unit_sha256"],
            "assignment_row_sha256": assignment["assignment_row_sha256"],
            "assigned_reviewer_id": assignment["reviewer_id"],
            "assigned_reviewer_identity_commitment_sha256": assignment["reviewer_identity_commitment_sha256"],
        }
        if any(row[field] != expected for field, expected in exact.items()):
            raise P0PresentedNeutralReviewError("review result identity mismatch")
        status = row["annotation_status"]
        if status not in ANNOTATION_STATUSES:
            raise P0PresentedNeutralReviewError("review result status invalid")
        decision = {
            "input_sequence": index,
            "annotation_status": status,
            "terminal_reason_code": row["terminal_reason_code"],
            "reviewer_id": None if status == "UNJUDGED" else row["assigned_reviewer_id"],
            "reviewed_at": row["reviewed_at"],
            "gold_spans": None if row["presented_gold_spans"] is None else [
                {field: span[field] for field in ("line_number", "character_span_start", "character_span_end", "utf8_byte_span_start", "utf8_byte_span_end", "evidence_text", "surface_text", "presented_definition_text")}
                for span in row["presented_gold_spans"]
            ],
        }
        expected = _build_result_row(decision, unit, assignment, precommit)
        if row != expected:
            raise P0PresentedNeutralReviewError("review result differs from exact recomputation")
        decisions.append(row)
    return decisions


def validate_review_receipt_bytes(
    raw: bytes,
    *,
    sampling_plan_raw: bytes,
    expected_sampling_plan_raw_sha256: str,
    bridge_inventory_raw: bytes,
    batch_precommit_raw: bytes,
    expected_batch_precommit_raw_sha256: str,
    results_raw: bytes,
    batch_receipt_raw: bytes,
    unreviewed_inventory_raw: bytes,
    reviewer_roster_raw: bytes,
    review_unit_inventory_raw: bytes,
    assignment_inventory_raw: bytes,
    review_precommit_raw: bytes,
    review_results_raw: bytes,
) -> dict[str, Any]:
    roster = _validate_roster(reviewer_roster_raw)
    units = _validate_units(review_unit_inventory_raw)
    assignments = _validate_assignments(assignment_inventory_raw, units, roster)
    precommit = _validate_precommit(
        review_precommit_raw,
        sampling_plan_raw=sampling_plan_raw,
        expected_sampling_plan_raw_sha256=expected_sampling_plan_raw_sha256,
        bridge_inventory_raw=bridge_inventory_raw,
        batch_precommit_raw=batch_precommit_raw,
        expected_batch_precommit_raw_sha256=expected_batch_precommit_raw_sha256,
        results_raw=results_raw,
        batch_receipt_raw=batch_receipt_raw,
        unreviewed_inventory_raw=unreviewed_inventory_raw,
        roster_raw=reviewer_roster_raw,
        units_raw=review_unit_inventory_raw,
        assignments_raw=assignment_inventory_raw,
    )
    result_rows = _validate_review_results(review_results_raw, units, assignments, precommit)
    row = _strict(_object(raw, "review receipt"), _RECEIPT_FIELDS, "review receipt")
    _false_authority(row, "review receipt")
    expected = _receipt_value(
        precommit_raw=review_precommit_raw,
        precommit=precommit,
        units_raw=review_unit_inventory_raw,
        units=units,
        assignments_raw=assignment_inventory_raw,
        results_raw=review_results_raw,
        result_rows=result_rows,
        results_sealed_at=row["review_results_sealed_at"],
        receipt_sealed_at=row["receipt_sealed_at"],
    )
    if raw != canonical_file_bytes(expected):
        raise P0PresentedNeutralReviewError("review receipt exact recomputation mismatch")
    return row


ARTIFACT_FIELDS = {
    "reviewer_row": sorted(_REVIEWER_FIELDS),
    "emitted_observation_subject": sorted(_EMITTED_SUBJECT_FIELDS),
    "review_unit_row": sorted(_UNIT_FIELDS),
    "assignment_row": sorted(_ASSIGNMENT_FIELDS),
    "review_precommit": sorted(_PRECOMMIT_FIELDS),
    "gold_span": sorted(_GOLD_FIELDS),
    "observation_adjudication": sorted(_ADJUDICATION_FIELDS),
    "review_result_row": sorted(_RESULT_FIELDS),
    "review_receipt": sorted(_RECEIPT_FIELDS),
}

COMPONENT_MANIFEST = {
    "schema_version": COMPONENT_MANIFEST_SCHEMA,
    "component": "p0_presented_neutral_review_accounting_v1_contract",
    "component_version": COMPONENT_VERSION,
    "record_origin": RECORD_ORIGIN,
    "upstream_component_manifest_sha256": batch_contract.COMPONENT_MANIFEST_SHA256,
    "reviewer_row_schema": REVIEWER_ROW_SCHEMA,
    "review_unit_row_schema": REVIEW_UNIT_ROW_SCHEMA,
    "assignment_row_schema": ASSIGNMENT_ROW_SCHEMA,
    "review_precommit_schema": REVIEW_PRECOMMIT_SCHEMA,
    "gold_span_schema": GOLD_SPAN_SCHEMA,
    "observation_adjudication_schema": OBSERVATION_ADJUDICATION_SCHEMA,
    "review_result_row_schema": REVIEW_RESULT_ROW_SCHEMA,
    "review_receipt_schema": REVIEW_RECEIPT_SCHEMA,
    "expected_input_count": EXPECTED_INPUT_COUNT,
    "annotation_statuses": list(ANNOTATION_STATUSES),
    "status_reason_codes": dict(_STATUS_REASON),
    "observation_verdicts": list(OBSERVATION_VERDICTS),
    "relation_kind": RELATION_KIND,
    "input_terminal_exactly_once": True,
    "unavailable_gold_and_arithmetic_are_null": True,
    "unjudged_gold_and_arithmetic_are_null": True,
    "judged_empty_gold_allowed": True,
    "core_error_input_retained": True,
    "physical_jsonl_order_required": True,
    "gold_span_capacity_policy": {
        "basis": "FULL_BOUNDED_REVIEW_DOCUMENT_MINIMUM_CANONICAL_RELATION_LINE",
        "max_document_chars": MAX_DOCUMENT_CHARS,
        "minimum_relation_line_chars": MIN_RELATION_LINE_CHARS,
        "max_gold_spans_per_input": MAX_GOLD_SPANS_PER_INPUT,
        "independent_of_parser_emission_limit": True,
        "overlong_strict_utf8_payload_terminal": "UNAVAILABLE_REQUIRED",
    },
    "forbidden_semantic_fields": sorted(_FORBIDDEN_SEMANTIC_FIELDS),
    "artifact_fields": ARTIFACT_FIELDS,
        "limits": {
            "max_reviewers": MAX_REVIEWERS,
            "max_gold_spans_per_input": MAX_GOLD_SPANS_PER_INPUT,
            "max_surface_chars": MAX_SURFACE_CHARS,
            "max_definition_chars": MAX_DEFINITION_CHARS,
            "max_json_bytes": MAX_JSON_BYTES,
        "max_jsonl_bytes": MAX_JSONL_BYTES,
    },
    "chronology": [
        "upstream_unreviewed_inventory_seal",
        "reviewer_roster_and_assignment_seal",
        "review_precommit",
        "presented_terminal_review_results",
        "review_accounting_receipt",
    ],
    "direct_io_capabilities": [],
    "actual_human_review_count": 0,
    "actual_human_unreviewed_input_count": EXPECTED_INPUT_COUNT,
    "actual_source_credit_count": 0,
    "actual_context_credit_count": 0,
    "metric_status": METRIC_STATUS,
    "descriptive_quality_metrics_allowed": False,
    "inferential_metrics_allowed": False,
    "complete_case_metrics_allowed": False,
    "semantic_metrics_allowed": False,
    "observation_rows_are_sampling_units": False,
    "sampling_unit": SAMPLING_UNIT,
    "denominator_policy": {
        "selected_input_itt_denominator": EXPECTED_INPUT_COUNT,
        "contextual_review_denominator": "ALL_SEALED_EMITTED_OBSERVATION_SUBJECTS",
        "full_payload_review_denominator": EXPECTED_INPUT_COUNT,
        "judged_subset_denominators": "EXACT_JUDGED_INPUT_SUBSET_DIAGNOSTIC_ONLY",
        "all_input_denominators": "INTEGER_ONLY_WHEN_ALL_40_PRESENTED_JUDGED_ELSE_NULL",
    },
    **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    "action_applied": False,
    "operational_effect": OPERATIONAL_EFFECT,
}
COMPONENT_MANIFEST_SHA256 = canonical_sha256(COMPONENT_MANIFEST)


__all__ = [
    "ANNOTATION_STATUSES",
    "ARTIFACT_FIELDS",
    "ASSIGNMENT_ROW_SCHEMA",
    "COMPONENT_MANIFEST",
    "COMPONENT_MANIFEST_SHA256",
    "COMPONENT_VERSION",
    "EXPECTED_INPUT_COUNT",
    "GATE_STATUS",
    "GOLD_SPAN_SCHEMA",
    "METRIC_STATUS",
    "OBSERVATION_ADJUDICATION_SCHEMA",
    "P0PresentedNeutralReviewError",
    "REVIEWER_ROW_SCHEMA",
    "REVIEW_PRECOMMIT_SCHEMA",
    "REVIEW_RECEIPT_SCHEMA",
    "REVIEW_RESULT_ROW_SCHEMA",
    "REVIEW_UNIT_ROW_SCHEMA",
    "build_assignment_inventory_bytes",
    "build_review_precommit_bytes",
    "build_review_unit_inventory_bytes",
    "build_reviewer_roster_bytes",
    "canonical_bytes",
    "canonical_file_bytes",
    "canonical_sha256",
    "execute_presented_review",
    "raw_sha256",
    "validate_review_receipt_bytes",
    "with_self_hash",
]
