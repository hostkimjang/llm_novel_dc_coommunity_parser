from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_adjusted_collateral_adjudication import TERMINAL_LABELS
from tools.build_adjusted_collateral_blind_packet import packet_row_digest, source_payload
from tools.build_full375_search_adjudication_gate import (
    SEARCH_TERMINAL_PACKET_VERSION,
    _canonical_hash,
    _public_state,
    _search_health,
    _search_health_issues,
    _source_hash,
    _terminal_issues,
)


BUILDER_VERSION = "search-terminal-consensus-ledger-v2"


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
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL row must be object: {path}:{line_no}")
            rows.append(value)
    return rows


def _load_result_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return _load_jsonl(path)
    value = _load_json(path)
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict):
        rows = next(
            (
                value[key]
                for key in ("results", "rows", "items")
                if isinstance(value.get(key), list)
            ),
            [value] if value.get("post_id") is not None else None,
        )
    else:
        rows = None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"runtime result must contain an object row list: {path}")
    return rows


def _required_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def _sha_text(value: Any, label: str) -> str:
    text = _required_text(value, label).lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{label} must be lowercase sha256")
    return text


def _post_id(value: Any, label: str) -> str:
    if isinstance(value, bool):
        raise ValueError(f"{label} post_id is invalid")
    return _required_text(value, f"{label} post_id")


def _index(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        post_id = _post_id(row.get("post_id"), label)
        if post_id in indexed:
            raise ValueError(f"{label} duplicate post_id: {post_id}")
        indexed[post_id] = row
    return indexed


def _review_rows(review: dict[str, Any], label: str) -> list[dict[str, Any]]:
    rows = review.get("rows")
    if not isinstance(rows, list):
        rows = review.get("decisions")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"{label} rows/decisions must be an object list")
    return rows


def _resolve_reference(path_text: Any) -> Path:
    candidate = Path(_required_text(path_text, "artifact path"))
    return (ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()


def _path_text(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _path_ref(
    path: Path,
    sha256: str,
    description_ko: str,
    *,
    row_count: int | None = None,
) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "path": _path_text(path),
        "sha256": sha256,
        "description_ko": description_ko,
    }
    if row_count is not None:
        ref["row_count"] = row_count
    return ref


def _ref_path(ref: dict[str, Any]) -> Any:
    return ref.get("path") or ref.get("packet_path") or ref.get("artifact_path")


def _ref_sha(ref: dict[str, Any]) -> Any:
    return ref.get("sha256") or ref.get("packet_sha256") or ref.get("artifact_sha256")


def _assert_artifact_ref(
    ref: Any,
    *,
    expected_path: Path,
    expected_sha256: str,
    label: str,
    expected_rows: int | None = None,
) -> None:
    if not isinstance(ref, dict):
        raise ValueError(f"{label} artifact binding missing")
    if _resolve_reference(_ref_path(ref)) != expected_path.resolve():
        raise ValueError(f"{label} path mismatch")
    if _sha_text(_ref_sha(ref), f"{label} sha256") != expected_sha256:
        raise ValueError(f"{label} sha256 mismatch")
    if expected_rows is not None:
        row_count = ref.get("row_count")
        if row_count is None:
            row_count = ref.get("packet_row_count")
        if row_count is None:
            row_count = ref.get("result_row_count")
        if row_count is None or isinstance(row_count, bool) or int(row_count) != expected_rows:
            raise ValueError(f"{label} row_count mismatch")


def _blind_root_packet_ref(review: dict[str, Any]) -> dict[str, Any]:
    scope = review.get("review_scope") if isinstance(review.get("review_scope"), dict) else {}
    if scope:
        return {
            "path": scope.get("packet_path"),
            "sha256": scope.get("packet_sha256"),
            "row_count": scope.get("packet_row_count"),
        }
    ref = review.get("packet")
    if isinstance(ref, dict):
        return ref
    return {
        "path": review.get("packet_path"),
        "sha256": review.get("packet_sha256"),
        "row_count": review.get("packet_row_count") or len(_review_rows(review, "blind review")),
    }


def _independent_root_ref(review: dict[str, Any], key: str) -> dict[str, Any] | None:
    aliases = {
        "packet": ("packet",),
        "template": ("template",),
        "result": ("runtime_result", "result"),
    }
    for name in aliases[key]:
        value = review.get(name)
        if isinstance(value, dict):
            return value
    for container_name in ("input_artifacts", "artifact_provenance", "bindings"):
        container = review.get(container_name)
        if not isinstance(container, dict):
            continue
        for name in aliases[key]:
            value = container.get(name)
            if isinstance(value, dict):
                return value
    if key == "packet" and review.get("packet_path"):
        return {
            "path": review.get("packet_path"),
            "sha256": review.get("packet_sha256"),
            "row_count": review.get("packet_row_count"),
        }
    return None


def _binding(row: dict[str, Any], *names: str) -> dict[str, Any]:
    for name in names:
        value = row.get(name)
        if isinstance(value, dict):
            return value
    return row


def _binding_value(row: dict[str, Any], field: str, *binding_names: str) -> Any:
    if field in row:
        return row.get(field)
    for name in binding_names:
        binding = row.get(name)
        if isinstance(binding, dict) and field in binding:
            return binding.get(field)
    return None


def _assert_row_packet_binding(
    review_row: dict[str, Any],
    *,
    packet_path: Path,
    packet_sha256: str,
    packet_row_number: int,
    packet_row_sha256: str,
    source_hash: str,
    label: str,
) -> None:
    binding = _binding(review_row, "binding", "packet_binding")
    path_value = binding.get("packet_path") or binding.get("path")
    sha_value = binding.get("packet_sha256") or binding.get("sha256")
    if _resolve_reference(path_value) != packet_path.resolve():
        raise ValueError(f"{label} packet path mismatch")
    if _sha_text(sha_value, f"{label} packet sha256") != packet_sha256:
        raise ValueError(f"{label} packet sha256 mismatch")
    bound_number = binding.get("packet_row_number")
    if bound_number is None:
        bound_number = binding.get("row_number")
    if isinstance(bound_number, bool) or int(bound_number or 0) != packet_row_number:
        raise ValueError(f"{label} packet row number mismatch")
    if _sha_text(binding.get("packet_row_sha256"), f"{label} packet row sha256") != packet_row_sha256:
        raise ValueError(f"{label} packet row sha256 mismatch")
    if _sha_text(binding.get("source_hash"), f"{label} source_hash") != source_hash:
        raise ValueError(f"{label} source_hash mismatch")


def _assert_independent_row_artifact_hashes(
    row: dict[str, Any],
    *,
    template_row_sha256: str,
    result_row_sha256: str,
    label: str,
) -> None:
    template_hash = _binding_value(
        row, "template_row_sha256", "binding", "packet_binding", "template_binding"
    )
    result_hash = _binding_value(
        row, "result_row_sha256", "binding", "packet_binding", "result_binding"
    )
    if _sha_text(template_hash, f"{label} template row sha256") != template_row_sha256:
        raise ValueError(f"{label} template row sha256 mismatch")
    if _sha_text(result_hash, f"{label} result row sha256") != result_row_sha256:
        raise ValueError(f"{label} result row sha256 mismatch")


def _row_text(row: dict[str, Any], label: str, *names: str) -> str:
    for name in names:
        text = str(row.get(name) or "").strip()
        if text:
            return text
    raise ValueError(f"{label} is required")


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        for row in rows
    )


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


def _markdown_bytes(report: dict[str, Any]) -> bytes:
    counts = report["counts"]
    excluded = report["excluded_rows"]
    excluded_lines = (
        "\n".join(
            f"- `{row['post_id']}`: `{row['exclusion_reason']}` - {row['reason_ko']}"
            for row in excluded
        )
        if excluded
        else "- 없음"
    )
    markdown = f"""# Search terminal 합의 ledger v2 보고서

## 결론

- builder gate: `{report['builder_gate']}`
- terminal consensus gate: `{report['terminal_consensus_gate']}`
- packet/template/result 바인딩: `PASS`
- packet 행: `{counts['packet']}`
- 합의 terminal 행: `{counts['consensus_terminal_safe']}`
- 제외 행: `{counts['excluded']}`
- production full-scan approval: `false`

## 합의 계약

블라인드 검토가 `terminal_safe=true`와 `classification=safe_no_public_terminal`을 모두 만족하고,
서로 다른 독립 검토자가 `terminal_safe=true`로 판정한 행만 immutable ledger에 포함했다.
packet, template, runtime result의 파일 SHA256과 각 행의 source/packet/template/result hash를 교차 검증했다.

## 제외 행

{excluded_lines}

## 산출물

- ledger: `{report['output_artifacts']['ledger']['path']}`
- JSON report: `{report['output_artifacts']['report']['path']}`
- Markdown report: `{report['output_artifacts']['markdown']['path']}`

## 승인 경계

이 보고서는 terminal 합의 ledger 생성 무결성만 증명한다. 제외 행은 해소 전 unreviewed/blocker로 남으며,
dashboard, queue 0, canary runtime 완료 또는 이 builder의 성공만으로 full-scan/production 승인을 뜻하지 않는다.
"""
    return markdown.encode("utf-8")


def _validate_expected_count(actual: int, expected: int | None, label: str) -> int:
    resolved = actual if expected is None else expected
    if isinstance(resolved, bool) or resolved < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    if actual != resolved:
        raise ValueError(f"{label} mismatch: {actual} != {resolved}")
    return resolved


def build_consensus(
    *,
    packet_path: Path,
    template_path: Path,
    blind_review_path: Path,
    independent_review_path: Path,
    result_path: Path,
    output_ledger_path: Path,
    output_report_path: Path,
    output_md_path: Path,
    expected_hashes: dict[str, str] | None = None,
    expected_packet_rows: int | None = None,
    expected_result_rows: int | None = None,
    expected_consensus_rows: int | None = None,
    expected_excluded_rows: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], bytes]:
    paths = {
        "packet": packet_path,
        "template": template_path,
        "blind_review": blind_review_path,
        "independent_review": independent_review_path,
        "result": result_path,
    }
    hashes: dict[str, str] = {}
    for label, path in paths.items():
        if not path.is_file():
            raise ValueError(f"{label} input missing: {path}")
        hashes[label] = file_sha256(path)
        if expected_hashes and expected_hashes.get(label) is not None:
            expected = _sha_text(expected_hashes[label], f"expected {label} sha256")
            if hashes[label] != expected:
                raise ValueError(f"{label} byte sha256 mismatch: {hashes[label]} != {expected}")

    packets = _load_jsonl(packet_path)
    templates = _load_jsonl(template_path)
    result_rows = _load_result_rows(result_path)
    blind_review = _load_json(blind_review_path)
    independent_review = _load_json(independent_review_path)
    if not isinstance(blind_review, dict) or not isinstance(independent_review, dict):
        raise ValueError("review roots must be objects")
    blind_rows = _review_rows(blind_review, "blind review")
    independent_rows = _review_rows(independent_review, "independent review")

    packet_count = _validate_expected_count(
        len(packets), expected_packet_rows, "expected packet rows"
    )
    _validate_expected_count(len(templates), packet_count, "template row count")
    _validate_expected_count(len(blind_rows), packet_count, "blind review row count")
    _validate_expected_count(
        len(independent_rows), packet_count, "independent review row count"
    )
    result_count = _validate_expected_count(
        len(result_rows), expected_result_rows, "expected result rows"
    )

    packet_by_id = _index(packets, "packet")
    template_by_id = _index(templates, "template")
    result_by_id = _index(result_rows, "runtime result")
    blind_by_id = _index(blind_rows, "blind review")
    independent_by_id = _index(independent_rows, "independent review")
    packet_ids = set(packet_by_id)
    for label, indexed in {
        "template": template_by_id,
        "blind review": blind_by_id,
        "independent review": independent_by_id,
    }.items():
        missing = sorted(packet_ids - set(indexed))
        extra = sorted(set(indexed) - packet_ids)
        if missing or extra:
            raise ValueError(f"{label} post_id set mismatch: missing={missing} extra={extra}")
    missing_result = sorted(packet_ids - set(result_by_id))
    if missing_result:
        raise ValueError(f"runtime result missing packet post_ids: {missing_result}")

    _assert_artifact_ref(
        _blind_root_packet_ref(blind_review),
        expected_path=packet_path,
        expected_sha256=hashes["packet"],
        expected_rows=packet_count,
        label="blind review packet",
    )
    for key, path, count in (
        ("packet", packet_path, packet_count),
        ("template", template_path, packet_count),
        ("result", result_path, result_count),
    ):
        _assert_artifact_ref(
            _independent_root_ref(independent_review, key),
            expected_path=path,
            expected_sha256=hashes[key],
            expected_rows=count,
            label=f"independent review {key}",
        )

    blind_reviewer = _required_text(blind_review.get("reviewer"), "blind reviewer")
    blind_model = _required_text(blind_review.get("model"), "blind model")
    blind_run_id = _required_text(blind_review.get("run_id"), "blind run_id")
    blind_review_id = _required_text(
        blind_review.get("review_id") or blind_run_id, "blind review_id"
    )
    independent_reviewer = _required_text(
        independent_review.get("reviewer"), "independent reviewer"
    )
    independent_review_id = _required_text(
        independent_review.get("review_id"), "independent review_id"
    )
    independent_reviewed_at = _required_text(
        independent_review.get("reviewed_at"), "independent reviewed_at"
    )
    if independent_review.get("role") != "independent_reviewer":
        raise ValueError("independent review role mismatch")
    if blind_reviewer == independent_reviewer:
        raise ValueError("blind and independent reviewer identities must differ")
    if blind_review_id == independent_review_id:
        raise ValueError("blind and independent review IDs must differ")

    refs = {
        "packet": _path_ref(packet_path, hashes["packet"], "원문 및 검색 관찰 packet", row_count=packet_count),
        "template": _path_ref(template_path, hashes["template"], "실제 runtime promotion contract template", row_count=packet_count),
        "blind_review": _path_ref(blind_review_path, hashes["blind_review"], "source-only 블라인드 검토"),
        "independent_review": _path_ref(independent_review_path, hashes["independent_review"], "독립 runtime/public-state 검토"),
        "result": _path_ref(result_path, hashes["result"], "원본 runtime result", row_count=result_count),
    }
    evidence_refs = [copy.deepcopy(refs[key]) for key in ("packet", "template", "blind_review", "independent_review", "result")]

    consensus: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    identity_tuples: set[tuple[str, str, str, str, str]] = set()
    for row_number, packet in enumerate(packets, 1):
        post_id = _post_id(packet.get("post_id"), "packet")
        template = template_by_id[post_id]
        runtime_row = result_by_id[post_id]
        blind = blind_by_id[post_id]
        independent = independent_by_id[post_id]

        if packet.get("packet_version") != SEARCH_TERMINAL_PACKET_VERSION:
            raise ValueError(f"packet version mismatch: {post_id}")
        source_hash = _sha_text(packet.get("source_hash"), f"packet source_hash {post_id}")
        packet_hash = _sha_text(
            packet.get("packet_row_sha256"), f"packet row sha256 {post_id}"
        )
        if packet_row_digest(packet) != packet_hash:
            raise ValueError(f"packet canonical row sha256 mismatch: {post_id}")
        runtime_source_hash = _source_hash(runtime_row)
        if runtime_source_hash != source_hash:
            raise ValueError(f"runtime result source_hash mismatch: {post_id}")
        if packet.get("source") != source_payload(runtime_row):
            raise ValueError(f"packet source payload mismatch: {post_id}")

        health = _search_health(runtime_row)
        expected_observation = {
            "status": health.get("status"),
            "queries_issued": health.get("queries_issued"),
            "degraded_zero": health.get("degraded_zero"),
            "degraded_recovered": health.get("degraded_recovered"),
            "unrecovered_degraded": health.get("unrecovered_degraded"),
            "schema_issues": _search_health_issues(health),
        }
        if packet.get("search_observation") != expected_observation:
            raise ValueError(f"packet search observation mismatch: {post_id}")
        if packet.get("allowed_classification") != "safe_no_public_terminal":
            raise ValueError(f"packet allowed classification mismatch: {post_id}")

        template_hash = canonical_sha256(template)
        result_hash = canonical_sha256(runtime_row)
        identity_tuple = (post_id, source_hash, packet_hash, template_hash, result_hash)
        if identity_tuple in identity_tuples:
            raise ValueError(f"duplicate bound identity tuple: {post_id}")
        identity_tuples.add(identity_tuple)

        template_source = _sha_text(template.get("source_hash"), f"template source_hash {post_id}")
        template_input = _sha_text(template.get("input_hash"), f"template input_hash {post_id}")
        if template_source != source_hash or template_input != source_hash:
            raise ValueError(f"template source/input hash mismatch: {post_id}")
        template_blind = template.get("blind_verdict")
        if not isinstance(template_blind, dict):
            raise ValueError(f"template blind verdict missing: {post_id}")
        _assert_artifact_ref(
            template_blind.get("packet_ref"),
            expected_path=packet_path,
            expected_sha256=hashes["packet"],
            label=f"template {post_id} packet",
        )
        if _sha_text(template_blind.get("packet_sha256"), f"template packet sha256 {post_id}") != hashes["packet"]:
            raise ValueError(f"template packet sha256 mismatch: {post_id}")
        if _sha_text(template_blind.get("packet_row_sha256"), f"template packet row sha256 {post_id}") != packet_hash:
            raise ValueError(f"template packet row sha256 mismatch: {post_id}")

        _assert_row_packet_binding(
            blind,
            packet_path=packet_path,
            packet_sha256=hashes["packet"],
            packet_row_number=row_number,
            packet_row_sha256=packet_hash,
            source_hash=source_hash,
            label=f"blind review {post_id}",
        )
        _assert_row_packet_binding(
            independent,
            packet_path=packet_path,
            packet_sha256=hashes["packet"],
            packet_row_number=row_number,
            packet_row_sha256=packet_hash,
            source_hash=source_hash,
            label=f"independent review {post_id}",
        )
        _assert_independent_row_artifact_hashes(
            independent,
            template_row_sha256=template_hash,
            result_row_sha256=result_hash,
            label=f"independent review {post_id}",
        )

        public = _public_state(runtime_row)
        if public.get("official_title") not in (None, "") or public.get("official_url") not in (None, ""):
            raise ValueError(f"runtime public identity is not null: {post_id}")
        if public.get("publish_allowed") is not False:
            raise ValueError(f"runtime publish_allowed is not false: {post_id}")
        if public.get("decision_bypassed_gate") is not False or public.get("trace_bypassed_gate") is not False:
            raise ValueError(f"runtime bypassed_gate is not false: {post_id}")
        if public.get("candidate_preserved") is not True:
            raise ValueError(f"runtime candidate preservation missing: {post_id}")

        expected_after = {
            "official_title": None,
            "official_url": None,
            "publish_allowed": False,
        }
        expected_before_after = {
            "before": {"source_hash": source_hash},
            "after": expected_after,
        }
        if template.get("promotion_decision") != public.get("decision"):
            raise ValueError(f"template promotion_decision mismatch: {post_id}")
        if template.get("publish_contract_trace") != public.get("trace"):
            raise ValueError(f"template publish_contract_trace mismatch: {post_id}")
        if template.get("before_after") != expected_before_after:
            raise ValueError(f"template before_after mismatch: {post_id}")
        expected_health_hash = _canonical_hash(health)
        if template.get("search_health_snapshot_sha256") != expected_health_hash:
            raise ValueError(f"template search health snapshot mismatch: {post_id}")

        blind_safe_value = blind.get("terminal_safe")
        independent_safe_value = independent.get("terminal_safe")
        if not isinstance(blind_safe_value, bool):
            raise ValueError(f"blind terminal_safe must be boolean: {post_id}")
        if not isinstance(independent_safe_value, bool):
            raise ValueError(f"independent terminal_safe must be boolean: {post_id}")
        blind_classification = _required_text(
            blind.get("classification"), f"blind classification {post_id}"
        )
        if blind_safe_value and blind_classification != "safe_no_public_terminal":
            raise ValueError(f"blind safe classification mismatch: {post_id}")
        if not blind_safe_value and blind_classification != "blocker":
            raise ValueError(f"blind blocker classification mismatch: {post_id}")

        blind_safe = blind_safe_value and blind_classification == "safe_no_public_terminal"
        independent_safe = independent_safe_value is True
        if not (blind_safe and independent_safe):
            if not blind_safe:
                exclusion_reason = "blind_blocker"
            elif not independent_safe:
                exclusion_reason = "independent_disagreement"
            else:
                exclusion_reason = "review_disagreement"
            excluded.append(
                {
                    "post_id": packet.get("post_id"),
                    "source_hash": source_hash,
                    "packet_row_sha256": packet_hash,
                    "template_row_sha256": template_hash,
                    "result_row_sha256": result_hash,
                    "exclusion_reason": exclusion_reason,
                    "reason_ko": "두 독립 검토의 안전 종결 합의가 없어 ledger에서 제외했다.",
                    "blind": {
                        "terminal_safe": blind_safe_value,
                        "classification": blind_classification,
                        "terminal_label": blind.get("terminal_label"),
                    },
                    "independent": {
                        "terminal_safe": independent_safe_value,
                        "classification": independent.get("classification"),
                        "terminal_label": independent.get("terminal_label"),
                    },
                }
            )
            continue

        independent_label = str(independent.get("terminal_label") or "").strip()
        terminal_label = independent_label if independent_label in TERMINAL_LABELS else "INFO_MISSING"
        blind_rationale = _row_text(
            blind, f"blind rationale {post_id}", "row_rationale", "rationale"
        )
        independent_rationale = _row_text(
            independent,
            f"independent rationale {post_id}",
            "row_rationale",
            "rationale",
        )
        blind_unblock = _row_text(
            blind, f"blind unblock condition {post_id}", "unblock_condition"
        )
        independent_unblock = _row_text(
            independent,
            f"independent unblock condition {post_id}",
            "unblock_condition",
        )
        observation = packet["search_observation"]
        missing_evidence = [
            f"검색 관찰 상태가 {observation.get('status')}이다.",
            f"unrecovered_degraded={observation.get('unrecovered_degraded')}이다.",
        ]
        missing_evidence.extend(
            f"검색 health 근거: {issue}"
            for issue in observation.get("schema_issues") or []
        )
        missing_evidence.append("공식 title/url 공개를 허용할 완결된 검색 근거가 없다.")

        ledger = {
            "post_id": packet.get("post_id"),
            "search_status": observation.get("status"),
            "source_hash": source_hash,
            "input_hash": source_hash,
            "terminal_label": terminal_label,
            "classification": "safe_no_public_terminal",
            "row_rationale": (
                f"블라인드 판정: {blind_rationale} 독립 판정: {independent_rationale}"
            ),
            "evidence_refs": copy.deepcopy(evidence_refs),
            "before_after": expected_before_after,
            "blind_verdict": {
                "blind": True,
                "method": "source_native_blind",
                "classification": "safe_no_public_terminal",
                "terminal_label": terminal_label,
                "reviewer": blind_reviewer,
                "model": blind_model,
                "run_id": blind_run_id,
                "review_id": blind_review_id,
                "packet_ref": copy.deepcopy(refs["packet"]),
                "packet_sha256": hashes["packet"],
                "packet_row_sha256": packet_hash,
                "review_artifact_ref": copy.deepcopy(refs["blind_review"]),
                "source_terminal_label": blind.get("terminal_label"),
                "row_rationale": blind_rationale,
                "evidence_basis": blind.get("evidence_basis"),
                "unblock_condition": blind_unblock,
            },
            "promotion_decision": copy.deepcopy(public["decision"]),
            "publish_contract_trace": copy.deepcopy(public["trace"]),
            "test_replay_artifacts": copy.deepcopy(evidence_refs),
            "attempted_lanes": [
                "packet source/search_observation 무결성 검증",
                "runtime result/publication contract exact binding",
                "source-only 블라인드 판정",
                "독립 runtime/public-state 안전성 판정",
            ],
            "missing_or_conflicting_evidence": missing_evidence,
            "search_health_snapshot_sha256": expected_health_hash,
            "candidate_unavailable_reason": template.get("candidate_unavailable_reason"),
            "publication_violation": False,
            "unblock_condition": (
                f"블라인드 조건: {blind_unblock} 독립 조건: {independent_unblock}"
            ),
            "independent_review": {
                "role": "independent_reviewer",
                "reviewer": independent_reviewer,
                "review_id": independent_review_id,
                "reviewed_at": independent_reviewed_at,
                "artifact_ref": copy.deepcopy(refs["independent_review"]),
                "terminal_safe": True,
                "terminal_label": independent.get("terminal_label"),
                "classification": independent.get("classification"),
                "row_rationale": independent_rationale,
                "evidence_basis": independent.get("evidence_basis"),
                "unblock_condition": independent_unblock,
            },
            "binding": {
                "packet_sha256": hashes["packet"],
                "packet_row_sha256": packet_hash,
                "template_sha256": hashes["template"],
                "template_row_sha256": template_hash,
                "result_sha256": hashes["result"],
                "result_row_sha256": result_hash,
            },
        }
        terminal_issues = _terminal_issues(ledger, runtime_row, public)
        if terminal_issues:
            raise ValueError(
                f"built ledger does not satisfy downstream terminal contract: {post_id}: "
                + ",".join(terminal_issues)
            )
        consensus.append(ledger)

    for position, label in (
        (1, "source_hash"),
        (2, "packet_row_sha256"),
        (3, "template_row_sha256"),
        (4, "result_row_sha256"),
    ):
        if len({identity[position] for identity in identity_tuples}) != packet_count:
            raise ValueError(f"duplicate bound {label}")
    _validate_expected_count(
        len(consensus), expected_consensus_rows, "expected consensus rows"
    )
    _validate_expected_count(len(excluded), expected_excluded_rows, "expected excluded rows")
    if len(consensus) + len(excluded) != packet_count:
        raise ValueError("consensus plus excluded coverage mismatch")

    ledger_bytes = _jsonl_bytes(consensus)
    ledger_sha = hashlib.sha256(ledger_bytes).hexdigest()
    terminal_gate = "GO" if not excluded else "NO-GO"
    report = {
        "report_type": "search_terminal_consensus_report_v2",
        "builder_version": BUILDER_VERSION,
        "builder_gate": "GO",
        "terminal_consensus_gate": terminal_gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary_ko": (
            f"packet {packet_count}행을 runtime result와 exact bind했다. 서로 다른 두 검토자가 "
            f"안전 종결에 합의한 {len(consensus)}행만 ledger에 포함했고, 합의가 없는 "
            f"{len(excluded)}행은 blocker/unreviewed로 남겼다."
        ),
        "determinism": {
            "wall_clock_fields_omitted": True,
            "output_order": "original_packet_order",
            "row_hash_contract": "json-sort-keys-compact-utf8",
            "intersection_rule": (
                "blind terminal_safe=true and classification=safe_no_public_terminal; "
                "independent terminal_safe=true; reviewer identities distinct"
            ),
        },
        "input_artifacts": refs,
        "trust_anchor_hashes_supplied": {
            key: bool(expected_hashes and expected_hashes.get(key)) for key in paths
        },
        "reviewers": {
            "blind": {
                "reviewer": blind_reviewer,
                "model": blind_model,
                "run_id": blind_run_id,
                "review_id": blind_review_id,
            },
            "independent": {
                "reviewer": independent_reviewer,
                "review_id": independent_review_id,
                "reviewed_at": independent_reviewed_at,
            },
            "reviewer_identities_distinct": True,
            "review_ids_distinct": True,
        },
        "identity_integrity": {
            "packet_post_id_set_exact_for_template": True,
            "packet_post_id_set_exact_for_blind_review": True,
            "packet_post_id_set_exact_for_independent_review": True,
            "packet_post_ids_present_in_runtime_result": True,
            "packet_source_payload_exact_to_runtime_result": True,
            "packet_template_result_row_hashes_exact": True,
            "unique_bound_identity_tuple_count": len(identity_tuples),
            "result_rows_outside_terminal_packet": result_count - packet_count,
        },
        "counts": {
            "packet": packet_count,
            "template": len(templates),
            "result": result_count,
            "blind_review": len(blind_rows),
            "independent_review": len(independent_rows),
            "consensus_terminal_safe": len(consensus),
            "excluded": len(excluded),
        },
        "consensus_post_ids": [row["post_id"] for row in consensus],
        "excluded_rows": excluded,
        "downstream_boundary": {
            "expected_terminal_ledger_rows": len(consensus),
            "expected_unreviewed_or_blocker_rows": len(excluded),
            "gate": terminal_gate,
            "reason_ko": (
                "모든 packet 행이 합의 terminal이면 GO이다. 제외 행이 있으면 별도 검색/판결 전 NO-GO이다."
            ),
            "dashboard_is_not_approval": True,
            "production_full_scan_approval": False,
        },
        "output_artifacts": {
            "ledger": {
                **_path_ref(output_ledger_path, ledger_sha, "합의 search terminal ledger"),
                "row_count": len(consensus),
                "exclusive_create_no_overwrite": True,
                "read_only_after_create": True,
            },
            "report": {"path": _path_text(output_report_path)},
            "markdown": {"path": _path_text(output_md_path)},
        },
    }
    markdown_bytes = _markdown_bytes(report)
    return consensus, report, markdown_bytes


def _write_exclusive_read_only(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def write_consensus_outputs(
    *,
    rows: list[dict[str, Any]],
    report: dict[str, Any],
    markdown_bytes: bytes,
    output_ledger_path: Path,
    output_report_path: Path,
    output_md_path: Path,
) -> None:
    outputs = (output_ledger_path, output_report_path, output_md_path)
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise FileExistsError(f"consensus outputs already exist; overwrite forbidden: {existing}")
    payloads = (_jsonl_bytes(rows), _json_bytes(report), markdown_bytes)
    created: list[Path] = []
    try:
        for path, payload in zip(outputs, payloads, strict=True):
            _write_exclusive_read_only(path, payload)
            created.append(path)
    except BaseException:
        for path in reversed(created):
            try:
                path.chmod(stat.S_IWRITE | stat.S_IREAD)
                path.unlink()
            except OSError:
                pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a generic immutable two-review search-terminal consensus ledger."
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--blind-review", type=Path, required=True)
    parser.add_argument("--independent-review", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output-ledger", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument("--expected-packet-sha256")
    parser.add_argument("--expected-template-sha256")
    parser.add_argument("--expected-result-sha256")
    parser.add_argument("--expected-packet-rows", type=int)
    parser.add_argument("--expected-result-rows", type=int)
    parser.add_argument("--expected-consensus-rows", type=int)
    parser.add_argument("--expected-excluded-rows", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expected_hashes = {
        key: value
        for key, value in {
            "packet": args.expected_packet_sha256,
            "template": args.expected_template_sha256,
            "result": args.expected_result_sha256,
        }.items()
        if value
    }
    rows, report, markdown_bytes = build_consensus(
        packet_path=args.packet.resolve(),
        template_path=args.template.resolve(),
        blind_review_path=args.blind_review.resolve(),
        independent_review_path=args.independent_review.resolve(),
        result_path=args.result.resolve(),
        output_ledger_path=args.output_ledger.resolve(),
        output_report_path=args.output_report.resolve(),
        output_md_path=args.output_md.resolve(),
        expected_hashes=expected_hashes,
        expected_packet_rows=args.expected_packet_rows,
        expected_result_rows=args.expected_result_rows,
        expected_consensus_rows=args.expected_consensus_rows,
        expected_excluded_rows=args.expected_excluded_rows,
    )
    write_consensus_outputs(
        rows=rows,
        report=report,
        markdown_bytes=markdown_bytes,
        output_ledger_path=args.output_ledger.resolve(),
        output_report_path=args.output_report.resolve(),
        output_md_path=args.output_md.resolve(),
    )
    print(
        json.dumps(
            {
                "builder_gate": report["builder_gate"],
                "terminal_consensus_gate": report["terminal_consensus_gate"],
                "ledger": {
                    "path": _path_text(args.output_ledger.resolve()),
                    "sha256": file_sha256(args.output_ledger.resolve()),
                    "row_count": len(rows),
                },
                "report": {
                    "path": _path_text(args.output_report.resolve()),
                    "sha256": file_sha256(args.output_report.resolve()),
                },
                "markdown": {
                    "path": _path_text(args.output_md.resolve()),
                    "sha256": file_sha256(args.output_md.resolve()),
                },
                "excluded": report["counts"]["excluded"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
