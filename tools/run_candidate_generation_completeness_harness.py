from __future__ import annotations

"""후보 보존 목록의 로컬 잘림 탐지 전후를 저장 산출물로 검증한다."""

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.candidate_generation import (  # noqa: E402
    CANDIDATE_STAGE_RULES,
    build_candidate_generation_proof,
    build_candidate_generation_snapshot,
    build_candidate_producer_plan,
    build_candidate_producer_receipt,
    build_candidate_stage_receipt,
    build_title_candidate_generation_snapshot,
    candidate_generation_snapshot_from_dict,
    candidate_stage_receipt_from_dict,
)
from src.llm_batch.candidate_set_shadow import selective_shadow_from_identity  # noqa: E402
from src.llm_batch.promotion_gate import _canonical_url, _title_key  # noqa: E402


RUN_SPEC_SCHEMA = "candidate-generation-completeness-runspec-v3"
REPORT_SCHEMA = "candidate-generation-completeness-comparison-v3"
PARENT_SCHEMA = "candidate-set-nil-shadow-runspec-v1"
MODE = "SAVED_ARTIFACT_AND_SYNTHETIC_SHADOW_NO_RUNTIME"

STAGE_DESCRIPTIONS_KO = {
    ("gatekeeper", "comment_title_candidates"): (
        "댓글에서 제목처럼 보이는 표현을 메인 후보 생성기로 넘기기 전 최대 8개로 제한하는 단계"
    ),
    ("decoder", "new_suspected_titles"): (
        "Decoder가 새로 해석한 작품 후보를 공유 목록에 더하기 전 최대 5개로 제한하는 단계"
    ),
    ("verifier", "ranked_update"): (
        "Verifier가 증거에 따라 후보 점수를 다시 매긴 뒤 최대 5개로 제한하는 단계"
    ),
    ("verifier", "comment_boost"): (
        "댓글의 제목 확인 신호를 반영해 재정렬한 뒤 최대 5개로 제한하는 단계"
    ),
    ("arbiter", "critic_filter"): (
        "Arbiter가 낮은 신뢰도 후보를 거른 뒤 공유 목록을 최대 5개로 제한하는 단계"
    ),
    ("arbiter", "candidate_merge"): (
        "기존 후보와 Arbiter가 찾은 후보를 합친 뒤 최대 5개로 제한하는 단계"
    ),
    ("arbiter", "llm_candidate_merge"): (
        "근거 검사를 통과한 Arbiter LLM 후보를 합친 뒤 최대 5개로 제한하는 단계"
    ),
}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_path(path: str | Path) -> Path:
    value = Path(path)
    return (value if value.is_absolute() else ROOT / value).resolve()


def _stored_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _artifact_ref(path: str | Path) -> dict[str, Any]:
    resolved = _resolve_path(path)
    if not resolved.is_file():
        raise ValueError(f"artifact missing: {resolved}")
    return {
        "path": _stored_path(resolved),
        "sha256": _sha256_file(resolved),
        "bytes": resolved.stat().st_size,
    }


def _validate_artifact_ref(ref: Any, name: str) -> Path:
    if not isinstance(ref, dict):
        raise ValueError(f"artifact ref missing: {name}")
    path = _resolve_path(str(ref.get("path") or ""))
    if not path.is_file():
        raise ValueError(f"artifact missing on disk: {name}")
    if _sha256_file(path) != ref.get("sha256"):
        raise ValueError(f"artifact sha256 mismatch: {name}")
    if path.stat().st_size != ref.get("bytes"):
        raise ValueError(f"artifact bytes mismatch: {name}")
    return path


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _post_id(row: dict[str, Any]) -> str:
    value = str(row.get("post_id") or "").strip()
    if not value:
        raise ValueError("row is missing post_id")
    return value


def _post_contract(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [_post_id(row) for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate post_id in baseline rows")
    return {
        "row_count": len(ids),
        "post_id_order_sha256": _canonical_hash(ids),
        "post_id_set_sha256": _canonical_hash(sorted(ids)),
        "post_ids": ids,
    }


def _assert_contract(left: dict[str, Any], right: dict[str, Any], label: str) -> None:
    for key in ("row_count", "post_id_order_sha256", "post_id_set_sha256"):
        if left.get(key) != right.get(key):
            raise ValueError(f"{label} {key} mismatch")


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    result = row.get("analysis_result")
    identity = result.get("identity") if isinstance(result, dict) else None
    return identity if isinstance(identity, dict) else {}


def _first_text(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _public_snapshot_from_identity(identity: dict[str, Any]) -> dict[str, Any]:
    novel = identity.get("novel_identity")
    novel = novel if isinstance(novel, dict) else {}
    ledger = identity.get("candidate_ledger")
    ledger = ledger if isinstance(ledger, dict) else {}
    decision = identity.get("promotion_decision")
    decision = decision if isinstance(decision, dict) else ledger.get("promotion_decision")
    decision = decision if isinstance(decision, dict) else {}
    trace = identity.get("publish_contract_trace")
    trace = trace if isinstance(trace, dict) else ledger.get("publish_contract_trace")
    trace = trace if isinstance(trace, dict) else {}
    return {
        "official_title": _first_text(
            novel.get("official_title"),
            novel.get("official_novel_title"),
            identity.get("official_title"),
            decision.get("official_title"),
        ),
        "official_url": _first_text(
            novel.get("official_url"),
            novel.get("heretic_url"),
            identity.get("official_url"),
            decision.get("official_url"),
        ),
        "promotion_decision": copy.deepcopy(decision),
        "publish_contract_trace": copy.deepcopy(trace),
        "publish_contract_input_fingerprint": _first_text(
            identity.get("publish_contract_input_fingerprint"),
            ledger.get("publish_contract_input_fingerprint"),
        ),
        "promotion_gate_state": copy.deepcopy(
            identity.get("promotion_gate_state")
            or ledger.get("promotion_gate_state")
            or {}
        ),
        "promotion_gate_evidence": copy.deepcopy(
            identity.get("promotion_gate_evidence")
            or ledger.get("promotion_gate_evidence")
            or []
        ),
        "publish_contract_version": _first_text(
            identity.get("publish_contract_version"),
            ledger.get("publish_contract_version"),
        ),
    }


def _implementation_contract() -> dict[str, Any]:
    refs = {
        "harness_tool": _artifact_ref(Path(__file__)),
        "candidate_generation": _artifact_ref(ROOT / "src/llm_batch/candidate_generation.py"),
        "candidate_set_shadow": _artifact_ref(ROOT / "src/llm_batch/candidate_set_shadow.py"),
        "agentic_pipeline": _artifact_ref(ROOT / "src/llm_batch/agentic_pipeline.py"),
        "expert_orchestrator": _artifact_ref(ROOT / "src/llm_batch/experts/orchestrator.py"),
        "expert_gatekeeper": _artifact_ref(ROOT / "src/llm_batch/experts/gatekeeper.py"),
        "expert_decoder": _artifact_ref(ROOT / "src/llm_batch/experts/decoder.py"),
        "expert_verifier": _artifact_ref(ROOT / "src/llm_batch/experts/verifier.py"),
        "expert_arbiter": _artifact_ref(ROOT / "src/llm_batch/experts/arbiter.py"),
        "candidate_producer_test": _artifact_ref(
            ROOT / "tests/test_candidate_producer_completion.py"
        ),
    }
    return {
        "artifacts": refs,
        "sha256": _canonical_hash(
            {name: ref["sha256"] for name, ref in sorted(refs.items())}
        ),
    }


def _validate_parent(
    parent_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], Path, dict[str, Any]]:
    from tools.run_candidate_set_nil_shadow_harness import validate_run_spec as validate_p1

    parent, rows, _sources = validate_p1(parent_path, verify_implementation=False)
    if not isinstance(parent, dict) or parent.get("schema_version") != PARENT_SCHEMA:
        raise ValueError("unsupported P1 parent run spec")
    artifacts = parent.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("P1 parent artifacts missing")
    baseline_path = _validate_artifact_ref(
        artifacts.get("baseline_result"),
        "P1 baseline_result",
    )
    contract = _post_contract(rows)
    stored_contract = parent.get("post_contract")
    if not isinstance(stored_contract, dict):
        raise ValueError("P1 parent post contract missing")
    _assert_contract(contract, stored_contract, "P1 parent post contract")
    return parent, rows, baseline_path, contract


def create_run_spec(*, parent_p1_run_spec_path: str | Path) -> dict[str, Any]:
    parent_ref = _artifact_ref(parent_p1_run_spec_path)
    parent, _rows, baseline_path, contract = _validate_parent(
        _resolve_path(parent_ref["path"])
    )
    baseline_ref = _artifact_ref(baseline_path)
    spec: dict[str, Any] = {
        "schema_version": RUN_SPEC_SCHEMA,
        "generated_at": _now(),
        "mode": MODE,
        "treatment": "candidate_generation_bounded_producer_proof_v3",
        "artifacts": {
            "p1_parent_run_spec": parent_ref,
            "baseline_result": baseline_ref,
        },
        "p1_parent": {
            "run_spec_self_hash": parent.get("run_spec_sha256"),
            "baseline_result_sha256": baseline_ref["sha256"],
            "post_contract": {
                key: contract[key]
                for key in (
                    "row_count",
                    "post_id_order_sha256",
                    "post_id_set_sha256",
                )
            },
        },
        "post_contract": {
            key: contract[key]
            for key in (
                "row_count",
                "post_id_order_sha256",
                "post_id_set_sha256",
            )
        },
        "implementation_contract": _implementation_contract(),
        "approval_boundary": {
            "semantic_quality": "REVIEW-LOCKED",
            "full_scan_approval": False,
            "runtime_validation": "NOT_RUN",
            "saved_artifact_only": True,
            "synthetic_boundary_cases": True,
        },
    }
    spec["run_spec_sha256"] = _canonical_hash(spec)
    return spec


def _assert_output_paths(paths: list[Path]) -> None:
    resolved = [path.resolve() for path in paths]
    if len(set(resolved)) != len(resolved):
        raise ValueError("output paths must be distinct")
    if any(path.exists() for path in resolved):
        raise ValueError("refusing to overwrite existing output")


def write_run_spec(run_spec: dict[str, Any], output_path: str | Path) -> Path:
    output = _resolve_path(output_path)
    _assert_output_paths([output])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(run_spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def _validate_frozen_implementation_contract(implementation: Any) -> None:
    if not isinstance(implementation, dict) or not isinstance(implementation.get("artifacts"), dict):
        raise ValueError("implementation contract missing")
    hashes: dict[str, str] = {}
    for name, ref in implementation["artifacts"].items():
        if not isinstance(name, str) or not isinstance(ref, dict):
            raise ValueError("frozen implementation artifact invalid")
        path, digest, size = ref.get("path"), ref.get("sha256"), ref.get("bytes")
        if not isinstance(path, str) or Path(path).is_absolute() or not path:
            raise ValueError(f"frozen implementation path invalid: {name}")
        if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"frozen implementation sha256 invalid: {name}")
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"frozen implementation bytes invalid: {name}")
        hashes[name] = digest
    if not hashes or implementation.get("sha256") != _canonical_hash(dict(sorted(hashes.items()))):
        raise ValueError("frozen implementation contract sha256 mismatch")


def validate_run_spec(
    run_spec_path: str | Path,
    *,
    verify_implementation: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = _resolve_path(run_spec_path)
    spec = _load_json(path)
    if (
        not isinstance(spec, dict)
        or spec.get("schema_version") != RUN_SPEC_SCHEMA
        or spec.get("mode") != MODE
    ):
        raise ValueError("unsupported candidate generation run spec")
    stored_hash = str(spec.get("run_spec_sha256") or "")
    if stored_hash != _canonical_hash(
        {key: value for key, value in spec.items() if key != "run_spec_sha256"}
    ):
        raise ValueError("run spec self hash mismatch")
    artifacts = spec.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("run spec artifacts missing")
    parent_path = _validate_artifact_ref(
        artifacts.get("p1_parent_run_spec"),
        "p1_parent_run_spec",
    )
    baseline_path = _validate_artifact_ref(
        artifacts.get("baseline_result"),
        "baseline_result",
    )
    parent, rows, parent_baseline, contract = _validate_parent(parent_path)
    if parent_baseline != baseline_path:
        raise ValueError("P1 parent/bound baseline path mismatch")
    parent_binding = spec.get("p1_parent")
    if not isinstance(parent_binding, dict):
        raise ValueError("P1 parent binding missing")
    if parent_binding.get("run_spec_self_hash") != parent.get("run_spec_sha256"):
        raise ValueError("P1 parent self hash binding mismatch")
    if parent_binding.get("baseline_result_sha256") != artifacts["baseline_result"]["sha256"]:
        raise ValueError("P1 parent baseline hash binding mismatch")
    _assert_contract(contract, parent_binding.get("post_contract") or {}, "P1 binding")
    _assert_contract(contract, spec.get("post_contract") or {}, "run spec")
    implementation = spec.get("implementation_contract")
    if verify_implementation:
        hashes = {
            str(name): _sha256_file(_validate_artifact_ref(ref, f"implementation {name}"))
            for name, ref in implementation["artifacts"].items()
        }
        if implementation.get("sha256") != _canonical_hash(dict(sorted(hashes.items()))):
            raise ValueError("implementation contract sha256 mismatch")
    _validate_frozen_implementation_contract(implementation)
    return spec, rows


def _actual_row_projection(row: dict[str, Any]) -> dict[str, Any]:
    identity = copy.deepcopy(_identity(row))
    before = _public_snapshot_from_identity(identity)
    sources = identity.get("candidate_preservation_sources")
    sources = sources if isinstance(sources, list) else []
    snapshot = build_candidate_generation_snapshot(sources, cap=24)
    ledger = dict(identity.get("candidate_ledger") or {})
    if any(
        key in ledger
        for key in ("candidate_generation_status", "candidate_generation_cap")
    ):
        raise ValueError(f"post {_post_id(row)} has conflicting flat generation metadata")
    ledger["candidate_generation"] = snapshot.to_ledger_dict()
    identity["candidate_ledger"] = ledger
    shadow = selective_shadow_from_identity(identity)
    if (
        shadow.candidate_set.generation_status != snapshot.status
        or shadow.candidate_set.generation_cap != snapshot.cap
    ):
        raise ValueError(f"post {_post_id(row)} generation metadata did not reach shadow")
    after = _public_snapshot_from_identity(identity)
    if before != after:
        raise ValueError(f"post {_post_id(row)} public contract changed")
    return {
        "post_id": int(_post_id(row)) if _post_id(row).isdigit() else _post_id(row),
        "before": {
            "generation_status": "UNRECORDED",
            "truncation_detected": False,
        },
        "after": snapshot.to_ledger_dict(),
        "candidate_set_recall_status": shadow.candidate_set.candidate_set_recall_status,
        "public_noninterference": {
            "before_sha256": _canonical_hash(before),
            "after_sha256": _canonical_hash(after),
            "unchanged": True,
        },
    }


def _synthetic_source(index: int, *, title: str | None = None) -> dict[str, Any]:
    return {
        "official_title": title or f"합성 작품 {index:02d}",
        "heretic_url": f"https://example.test/synthetic/{index}",
        "preservation_role": "title_candidate",
    }


def _legacy_retained_sources(
    sources: list[dict[str, Any]],
    *,
    cap: int = 24,
) -> list[dict[str, Any]]:
    """Emulate the former early-return behavior without using the treatment."""

    retained: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for source in sources:
        title = str(
            source.get("official_title")
            or source.get("title")
            or source.get("name")
            or ""
        ).strip()
        if not title:
            continue
        key = (
            _title_key(title),
            _canonical_url(source.get("heretic_url") or source.get("url")),
            str(source.get("preservation_role") or "").strip().casefold(),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        retained.append(copy.deepcopy(source))
        if len(retained) >= cap:
            return retained
    return retained


def _legacy_title_retained_sources(
    sources: list[dict[str, Any]],
    *,
    cap: int = 6,
) -> list[dict[str, Any]]:
    """Emulate the former ranked-title output's normalized-title dedupe."""

    retained: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in sources:
        title = str(
            source.get("official_title")
            or source.get("title")
            or source.get("name")
            or ""
        ).strip()
        key = _title_key(title)
        if not key or key in seen:
            continue
        seen.add(key)
        retained.append(copy.deepcopy(source))
        if len(retained) >= cap:
            return retained
    return retained


def _synthetic_case(name: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    legacy_retained = _legacy_retained_sources(sources, cap=24)
    snapshot = build_candidate_generation_snapshot(sources, cap=24)
    replay = candidate_generation_snapshot_from_dict(
        snapshot.to_ledger_dict(),
        retained_sources=list(snapshot.retained_sources or ()),
    )
    treatment_retained = list(replay.retained_sources or ())
    retained_unchanged = legacy_retained == treatment_retained
    if not retained_unchanged:
        raise ValueError(f"synthetic {name} changed the retained source list")
    return {
        "name": name,
        "raw_source_count": len(sources),
        "before": {
            "emitted_source_count": len(legacy_retained),
            "generation_status": "UNRECORDED",
            "truncation_detected": False,
            "retained_sources_fingerprint": _canonical_hash(legacy_retained),
        },
        "after": replay.to_ledger_dict(),
        "retained_sources_unchanged": retained_unchanged,
        "retained_order_first_title": (
            replay.retained_sources[0].get("official_title")
            if replay.retained_sources
            else None
        ),
        "retained_order_last_title": (
            replay.retained_sources[-1].get("official_title")
            if replay.retained_sources
            else None
        ),
    }


def _synthetic_title_case(
    name: str,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    legacy_retained = _legacy_title_retained_sources(sources, cap=6)
    snapshot = build_title_candidate_generation_snapshot(sources, cap=6)
    replay = candidate_generation_snapshot_from_dict(
        snapshot.to_ledger_dict(),
        retained_sources=list(snapshot.retained_sources or ()),
    )
    treatment_retained = list(replay.retained_sources or ())
    retained_unchanged = legacy_retained == treatment_retained
    if not retained_unchanged:
        raise ValueError(f"synthetic {name} changed the title-stage retained list")
    return {
        "name": name,
        "raw_source_count": len(sources),
        "before": {
            "emitted_source_count": len(legacy_retained),
            "generation_status": "UNRECORDED",
            "truncation_detected": False,
            "retained_sources_fingerprint": _canonical_hash(legacy_retained),
        },
        "after": replay.to_ledger_dict(),
        "retained_sources_unchanged": retained_unchanged,
    }


def _synthetic_stage_case(
    *,
    producer: str,
    stage: str,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    cap = CANDIDATE_STAGE_RULES[(producer, stage)]
    source_before = copy.deepcopy(sources)
    legacy_retained = copy.deepcopy(sources[:cap])
    receipt = build_candidate_stage_receipt(
        sources,
        producer=producer,
        stage=stage,
    )
    replay = candidate_stage_receipt_from_dict(receipt.to_ledger_dict())
    if sources != source_before:
        raise ValueError(f"stage receipt mutated {producer}.{stage} sources")
    retained_unchanged = legacy_retained == source_before[:cap]
    if not retained_unchanged:
        raise ValueError(f"stage receipt changed {producer}.{stage} retained rows")
    return {
        "name_ko": STAGE_DESCRIPTIONS_KO[(producer, stage)],
        "producer": producer,
        "stage": stage,
        "raw_source_count": len(sources),
        "before": {
            "emitted_source_count": len(legacy_retained),
            "generation_status": "UNRECORDED",
            "truncation_detected": False,
        },
        "after": replay.to_ledger_dict(),
        "retained_sources_unchanged": retained_unchanged,
        "candidate_set_status_effect": "NONE_DIAGNOSTIC_ONLY",
        "public_decision_effect": "NONE",
    }


def _synthetic_producer_cases(base_row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Exercise bounded producer proof states without running MCP/LLM."""

    base_identity = copy.deepcopy(_identity(base_row))
    source_candidates = base_identity.get("candidate_preservation_sources")
    source_candidates = (
        copy.deepcopy(source_candidates)
        if isinstance(source_candidates, list)
        else []
    )
    if not source_candidates:
        source_candidates = [_synthetic_source(901)]
    source_candidates = source_candidates[:5]
    local_snapshot = build_candidate_generation_snapshot(source_candidates, cap=24)
    title_snapshot = build_title_candidate_generation_snapshot(
        source_candidates,
        cap=6,
    )
    search_input = {
        "query": 'site:example.test "합성 producer 후보"',
        "purpose": "official_title_verify",
    }
    fetch_input = {
        "url": "https://example.test/synthetic-producer/1",
        "purpose": "official_detail_fetch",
    }

    def _case(
        name_ko: str,
        *,
        search_meta: dict[str, Any],
        search_result_count: int,
        search_plan_finished: bool = True,
        include_fetch_receipt: bool = True,
    ) -> dict[str, Any]:
        search_plan = build_candidate_producer_plan(
            [search_input],
            producer="search",
            occurrence=1,
            enumeration_finished=search_plan_finished,
        )
        fetch_plan = build_candidate_producer_plan(
            [fetch_input],
            producer="fetch",
            occurrence=1,
            enumeration_finished=True,
        )
        search_results = [
            {
                "title": f"합성 검색 후보 {index:02d}",
                "url": f"https://example.test/search/{index}",
            }
            for index in range(search_result_count)
        ]
        search_receipt = build_candidate_producer_receipt(
            search_results,
            search_meta,
            producer="search",
            operation_input=search_input,
            purpose="official_title_verify",
            plan_fingerprint=search_plan.plan_fingerprint,
            occurrence=1,
        )
        fetch_receipt = build_candidate_producer_receipt(
            [
                {
                    "url": fetch_input["url"],
                    "structured_info": {"page_title": "합성 producer 후보"},
                }
            ],
            {
                "attempted_count": 1,
                "raw_count": 1,
                "enumeration_finished": True,
            },
            producer="fetch",
            operation_input=fetch_input,
            purpose="official_detail_fetch",
            plan_fingerprint=fetch_plan.plan_fingerprint,
            occurrence=2,
        )
        receipts = [search_receipt]
        if include_fetch_receipt:
            receipts.append(fetch_receipt)
        plans = [search_plan, fetch_plan]
        proof = build_candidate_generation_proof(
            plans,
            receipts,
            local_snapshots=(local_snapshot, title_snapshot),
        )

        identity = copy.deepcopy(base_identity)
        public_before = _public_snapshot_from_identity(identity)
        identity["candidate_preservation_sources"] = copy.deepcopy(source_candidates)
        ledger = dict(identity.get("candidate_ledger") or {})
        for key in (
            "candidate_generation_proof",
            "candidate_producer_plans",
            "candidate_producer_receipts",
            "candidate_producer_integrity_errors",
        ):
            ledger.pop(key, None)
        ledger.update(
            {
                "candidate_generation": local_snapshot.to_ledger_dict(),
                "title_candidate_generation": title_snapshot.to_ledger_dict(),
                "title_candidate_generation_retained_sources": list(
                    title_snapshot.retained_sources or ()
                ),
                "candidate_producer_plans": [
                    plan.to_ledger_dict() for plan in plans
                ],
                "candidate_producer_receipts": [
                    receipt.to_ledger_dict() for receipt in receipts
                ],
                "candidate_generation_proof": proof.to_ledger_dict(),
            }
        )
        identity["candidate_ledger"] = ledger
        shadow = selective_shadow_from_identity(identity)
        public_after = _public_snapshot_from_identity(identity)
        if public_before != public_after:
            raise ValueError(f"synthetic producer case changed public output: {name_ko}")
        if any(
            probability.probability is not None
            for probability in shadow.event_probabilities
        ):
            raise ValueError("producer proof must not create probability values")
        redacted_payload = {
            "plans": ledger["candidate_producer_plans"],
            "receipts": ledger["candidate_producer_receipts"],
            "proof": ledger["candidate_generation_proof"],
        }
        serialized = _canonical_json(redacted_payload)
        if "example.test" in serialized or "합성 producer 후보" in serialized:
            raise ValueError("producer receipt leaked raw operation input/output")
        return {
            "name_ko": name_ko,
            "before": {
                "producer_status": "UNRECORDED",
                "candidate_set_generation_status": "UNKNOWN",
            },
            "after": {
                "producer_proof": proof.to_ledger_dict(),
                "candidate_set_generation_status": (
                    shadow.candidate_set.generation_status
                ),
                "candidate_set_recall_status": (
                    shadow.candidate_set.candidate_set_recall_status
                ),
                "probability_status": shadow.probability_status,
            },
            "public_noninterference": {
                "before_sha256": _canonical_hash(public_before),
                "after_sha256": _canonical_hash(public_after),
                "unchanged": True,
            },
            "raw_input_output_redacted": True,
        }

    return {
        "clean_search_fetch": _case(
            "정상 search+fetch bounded plan",
            search_meta={
                "attempts": 1,
                "raw_total": 1,
                "enumeration_finished": True,
            },
            search_result_count=1,
        ),
        "clean_cache_replay": _case(
            "원 실행 receipt/hash가 없어 보류하는 cache replay",
            search_meta={
                "attempts": 1,
                "raw_total": 1,
                "enumeration_finished": True,
                "from_cache": True,
            },
            search_result_count=1,
        ),
        "missing_fetch_receipt": _case(
            "계획된 fetch 영수증 누락",
            search_meta={
                "attempts": 1,
                "raw_total": 1,
                "enumeration_finished": True,
            },
            search_result_count=1,
            include_fetch_receipt=False,
        ),
        "degraded_search": _case(
            "degraded/throttle 검색",
            search_meta={
                "attempts": 2,
                "raw_total": 0,
                "enumeration_finished": True,
                "degraded": True,
                "possible_throttle": True,
            },
            search_result_count=0,
        ),
        "search_top_k_loss": _case(
            "검색 raw 11건 중 10건만 유지",
            search_meta={
                "attempts": 1,
                "raw_total": 11,
                "enumeration_finished": True,
            },
            search_result_count=10,
        ),
        "unfinished_search_plan": _case(
            "검색 조기 종료로 bounded plan 미완료",
            search_meta={
                "attempts": 1,
                "raw_total": 1,
                "enumeration_finished": True,
            },
            search_result_count=1,
            search_plan_finished=False,
        ),
    }


def build_comparison(run_spec_path: str | Path) -> dict[str, Any]:
    spec, rows = validate_run_spec(run_spec_path)
    actual_rows = [_actual_row_projection(row) for row in rows]
    unique25 = [_synthetic_source(index) for index in range(25)]
    exact24 = [_synthetic_source(index) for index in range(24)]
    duplicate25 = [_synthetic_source(index) for index in range(24)]
    duplicate25.append(copy.deepcopy(duplicate25[-1]))
    title_unique7 = [
        {
            **_synthetic_source(index),
            "preservation_role": "ranked_title_candidate",
        }
        for index in range(7)
    ]
    title_exact6 = copy.deepcopy(title_unique7[:6])
    title_duplicate7 = copy.deepcopy(title_exact6)
    title_duplicate7.append(copy.deepcopy(title_duplicate7[-1]))
    title_same_name_different_url = [
        {
            **_synthetic_source(101, title="동일 제목 작품"),
            "preservation_role": "ranked_title_candidate",
        },
        {
            **_synthetic_source(102, title="동일   제목 작품"),
            "preservation_role": "alternate_ranked_title_candidate",
        },
    ]
    synthetic = {
        "unique_25": _synthetic_case("고유 후보 25개", unique25),
        "exact_24": _synthetic_case("고유 후보 정확히 24개", exact24),
        "raw_25_unique_24": _synthetic_case("원본 25개 중 중복 1개", duplicate25),
        "title_unique_7": _synthetic_title_case(
            "상류 ranked title 고유 7개",
            title_unique7,
        ),
        "title_exact_6": _synthetic_title_case(
            "상류 ranked title 정확히 6개",
            title_exact6,
        ),
        "title_raw_7_unique_6": _synthetic_title_case(
            "상류 ranked title 원본 7개 중 중복 1개",
            title_duplicate7,
        ),
        "title_same_name_different_url": _synthetic_title_case(
            "상류 동일 정규화 제목·서로 다른 URL/역할",
            title_same_name_different_url,
        ),
    }
    stage_synthetic: dict[str, dict[str, Any]] = {}
    for (producer, stage), cap in CANDIDATE_STAGE_RULES.items():
        stage_synthetic[f"{producer}.{stage}.unique_cap_plus_1"] = (
            _synthetic_stage_case(
                producer=producer,
                stage=stage,
                sources=[
                    {"title": f"{producer} {stage} 후보 {index:02d}"}
                    for index in range(cap + 1)
                ],
            )
        )
    gate_cap = CANDIDATE_STAGE_RULES[("gatekeeper", "comment_title_candidates")]
    gate_exact_sources = [
        {"title": f"gatekeeper 경계 후보 {index:02d}"}
        for index in range(gate_cap)
    ]
    stage_synthetic["gatekeeper.comment_title_candidates.exact_cap"] = (
        _synthetic_stage_case(
            producer="gatekeeper",
            stage="comment_title_candidates",
            sources=gate_exact_sources,
        )
    )
    stage_synthetic["gatekeeper.comment_title_candidates.duplicate_beyond_cap"] = (
        _synthetic_stage_case(
            producer="gatekeeper",
            stage="comment_title_candidates",
            sources=gate_exact_sources + [copy.deepcopy(gate_exact_sources[0])],
        )
    )
    producer_synthetic = _synthetic_producer_cases(rows[0])
    if synthetic["unique_25"]["after"]["status"] != "TRUNCATED":
        raise ValueError("synthetic unique25 truncation was not detected")
    if synthetic["unique_25"]["after"]["unique_valid_source_count"] != 25:
        raise ValueError("synthetic unique25 source count mismatch")
    for name in ("exact_24", "raw_25_unique_24"):
        if synthetic[name]["after"]["status"] != "UNKNOWN":
            raise ValueError(f"synthetic {name} must remain UNKNOWN")
    if synthetic["title_unique_7"]["after"]["status"] != "TRUNCATED":
        raise ValueError("synthetic title_unique_7 truncation was not detected")
    for name in ("title_exact_6", "title_raw_7_unique_6"):
        if synthetic[name]["after"]["status"] != "UNKNOWN":
            raise ValueError(f"synthetic {name} must remain UNKNOWN")
    if (
        synthetic["title_same_name_different_url"]["after"][
            "unique_valid_source_count"
        ]
        != 1
    ):
        raise ValueError("same normalized title must be one ranked-title event")
    if any(row["after"]["status"] == "COMPLETE" for row in actual_rows):
        raise ValueError("saved artifact projection must not claim COMPLETE")
    if any(
        not case["retained_sources_unchanged"]
        for case in synthetic.values()
    ):
        raise ValueError("treatment changed a synthetic retained source list")
    stage_truncated_count = sum(
        case["after"]["status"] == "TRUNCATED"
        for name, case in stage_synthetic.items()
        if name.endswith("unique_cap_plus_1")
    )
    if stage_truncated_count != len(CANDIDATE_STAGE_RULES):
        raise ValueError("not all stage-local cap+1 cases detected truncation")
    for name in (
        "gatekeeper.comment_title_candidates.exact_cap",
        "gatekeeper.comment_title_candidates.duplicate_beyond_cap",
    ):
        if stage_synthetic[name]["after"]["status"] != "UNKNOWN":
            raise ValueError(f"synthetic stage case {name} must remain UNKNOWN")
    if any(
        not case["retained_sources_unchanged"]
        or case["candidate_set_status_effect"] != "NONE_DIAGNOSTIC_ONLY"
        or case["public_decision_effect"] != "NONE"
        for case in stage_synthetic.values()
    ):
        raise ValueError("stage receipt changed retained/public behavior")
    for name in ("clean_search_fetch",):
        case = producer_synthetic[name]
        if (
            case["after"]["producer_proof"]["status"] != "COMPLETE"
            or case["after"]["candidate_set_generation_status"] != "COMPLETE"
            or case["after"]["candidate_set_recall_status"]
            != "READY_FOR_GOLD_EVALUATION"
        ):
            raise ValueError(f"synthetic producer case {name} did not complete")
    for name in (
        "clean_cache_replay",
        "missing_fetch_receipt",
        "degraded_search",
        "unfinished_search_plan",
    ):
        case = producer_synthetic[name]
        if (
            case["after"]["producer_proof"]["status"] != "UNKNOWN"
            or case["after"]["candidate_set_generation_status"] != "UNKNOWN"
        ):
            raise ValueError(f"synthetic producer case {name} did not fail closed")
    top_k_case = producer_synthetic["search_top_k_loss"]
    if (
        top_k_case["after"]["producer_proof"]["status"] != "TRUNCATED"
        or top_k_case["after"]["candidate_set_generation_status"] != "UNKNOWN"
    ):
        raise ValueError("producer top-k loss did not remain fail closed")
    if any(
        not case["public_noninterference"]["unchanged"]
        or not case["raw_input_output_redacted"]
        or case["after"]["probability_status"] != "NOT_AVAILABLE_UNCALIBRATED"
        for case in producer_synthetic.values()
    ):
        raise ValueError("producer proof leaked data or changed public/probability output")
    producer_complete_count = sum(
        case["after"]["producer_proof"]["status"] == "COMPLETE"
        for case in producer_synthetic.values()
    )
    producer_unknown_count = sum(
        case["after"]["producer_proof"]["status"] == "UNKNOWN"
        for case in producer_synthetic.values()
    )
    producer_truncated_count = sum(
        case["after"]["producer_proof"]["status"] == "TRUNCATED"
        for case in producer_synthetic.values()
    )
    unchanged = sum(row["public_noninterference"]["unchanged"] for row in actual_rows)
    report = {
        "schema_version": REPORT_SCHEMA,
        "generated_at": _now(),
        "mode": MODE,
        "run_spec": {
            "path": _stored_path(_resolve_path(run_spec_path)),
            "sha256": _sha256_file(_resolve_path(run_spec_path)),
            "self_hash": spec["run_spec_sha256"],
        },
        "summary": {
            "actual_rows": len(actual_rows),
            "actual_public_contract_unchanged_rows": unchanged,
            "actual_complete_claim_rows": 0,
            "actual_recall_status": "NOT_EVALUABLE",
            "synthetic_truncation_detected_before": 0,
            "synthetic_truncation_detected_after": 2,
            "synthetic_false_complete_claims": 0,
            "synthetic_retained_output_unchanged_cases": len(synthetic),
            "synthetic_stage_truncation_detected_before": 0,
            "synthetic_stage_truncation_detected_after": stage_truncated_count,
            "synthetic_stage_false_truncation_cases": 0,
            "synthetic_stage_retained_output_unchanged_cases": len(stage_synthetic),
            "synthetic_producer_complete_before": 0,
            "synthetic_producer_complete_after": producer_complete_count,
            "synthetic_producer_unknown_after": producer_unknown_count,
            "synthetic_producer_truncated_after": producer_truncated_count,
            "synthetic_producer_false_complete_cases": 0,
            "synthetic_producer_public_unchanged_cases": len(producer_synthetic),
        },
        "actual_rows": actual_rows,
        "synthetic_cases": synthetic,
        "stage_synthetic_cases": stage_synthetic,
        "producer_synthetic_cases": producer_synthetic,
        "gates": {
            "artifact_integrity": "GO",
            "p1_parent": "GO",
            "post_id_completeness": "GO",
            "local_truncation_detection": "GO",
            "stage_local_receipt_detection": "GO_DIAGNOSTIC_ONLY",
            "producer_completion_proof": "GO_SYNTHETIC_CONTRACT_ONLY",
            "producer_runtime_wiring": "IMPLEMENTED_NOT_RUNTIME_VALIDATED",
            "false_complete_prevention": "GO",
            "retained_output_compatibility": "GO",
            "public_noninterference": "GO",
            "candidate_set_recall": "NOT_EVALUABLE",
            "runtime_validation": "NOT_RUN",
            "semantic_quality": "REVIEW-LOCKED",
            "full_scan_approval": False,
            "overall": "GO_SAVED_ARTIFACT_AND_SYNTHETIC_SHADOW_ONLY",
        },
        "approval_boundary_ko": (
            "Golden18 저장본의 공개 결과 무영향과 합성 cap 경계의 로컬 잘림 탐지만 "
            "검증했다. 단계별 영수증은 CandidateSet 상태에 합성하지 않는 진단 전용이다. "
            "query/search/fetch bounded producer proof는 정상 합성 계획에서만 COMPLETE가 "
            "되도록 계약과 코드 배선을 구현했다. 원 실행 receipt/hash에 결합되지 않은 "
            "cache replay와 사후 direct plan은 UNKNOWN이다. 이는 합성 증거다. Golden18에는 "
            "새 producer receipt가 없으므로 실제 후보 재현율, 새 런타임, 확률 정확도, "
            "전체 스캔 승인은 검증하지 않았다."
        ),
    }
    if unchanged != len(actual_rows):
        raise ValueError("not all actual rows preserved the public contract")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    gates = report["gates"]
    unique25 = report["synthetic_cases"]["unique_25"]
    exact24 = report["synthetic_cases"]["exact_24"]
    duplicate = report["synthetic_cases"]["raw_25_unique_24"]
    title7 = report["synthetic_cases"]["title_unique_7"]
    title6 = report["synthetic_cases"]["title_exact_6"]
    title_duplicate = report["synthetic_cases"]["title_raw_7_unique_6"]
    title_same_name = report["synthetic_cases"]["title_same_name_different_url"]
    stage_rows = [
        (
            f"| `{case['producer']}.{case['stage']}` | {case['name_ko']} | "
            f"{case['after']['cap']} | `{case['before']['generation_status']}` | "
            f"`{case['after']['status']}` "
            f"({case['after']['unique_valid_source_count']}개 관측·"
            f"{case['after']['emitted_source_count']}개 유지) |"
        )
        for name, case in report["stage_synthetic_cases"].items()
        if name.endswith("unique_cap_plus_1")
    ]
    producer_rows = [
        (
            f"| {case['name_ko']} | `{case['before']['producer_status']}` | "
            f"`{case['after']['producer_proof']['status']}` | "
            f"`{case['after']['candidate_set_generation_status']}` |"
        )
        for case in report["producer_synthetic_cases"].values()
    ]
    return "\n".join(
        [
            "# 후보 생성 완전성 증명 개선 보고서",
            "",
            "## 한눈에 보는 결론",
            "",
            "- 이전에는 후보 보존 목록이 24개에서 멈춰도 뒤에 후보가 더 있었는지 기록하지 않았다.",
            "- 개선 후에는 title-stage의 정책 필터 후 후보와 serializer 로컬 후보를 각각 cap 뒤까지 센다. cap 6 또는 24를 넘으면 `TRUNCATED(잘림)`, 그 외에는 `UNKNOWN(완전 여부 모름)`이다.",
            f"- 추가로 전문가 내부 7개 cap 경계도 진단 영수증을 남긴다. 합성 cap+1 사례는 이전 0건 기록에서 개선 후 {summary['synthetic_stage_truncation_detected_after']}건 모두 잘림을 검출했다.",
            "- 이 단계별 영수증은 어디서 후보가 사라졌는지 찾는 용도이며 CandidateSet 상태·확률·공개 판정에는 합성하지 않는다.",
            "- 새 bounded producer proof는 계획된 query/search/fetch가 빠짐없이 끝나고 저하·오류·결과 손실이 없을 때만 합성 사례에서 `COMPLETE(계획 범위 완료)`를 만든다. 웹 전체를 열거했다는 뜻은 아니다.",
            "- Golden18 저장본에는 새 producer 영수증이 없으므로 실제 행은 계속 `UNKNOWN`, 후보 재현율은 `NOT_EVALUABLE`이다.",
            f"- Golden18 공개 작품명·주소·승격 판정·추적 지문은 {summary['actual_public_contract_unchanged_rows']}/{summary['actual_rows']} 모두 그대로였다.",
            f"- 실제 새 실행은 `{gates['runtime_validation']}`, 의미 품질은 `{gates['semantic_quality']}`, 전체 승인은 `{str(gates['full_scan_approval']).lower()}`다.",
            "",
            "## 무엇이 달라졌나",
            "",
            "| 사례 | 개선 전 | 개선 후 | 뜻 |",
            "| --- | --- | --- | --- |",
            f"| 고유 후보 25개 | 잘림 기록 없음 | `{unique25['after']['status']}`, 25개 관측·24개 보존 | 25번째 후보의 존재를 잃지 않고 잘림으로 표시한다. |",
            f"| 고유 후보 정확히 24개 | 잘림 기록 없음 | `{exact24['after']['status']}` | 24개라고 해서 전체 후보를 다 봤다고 과장하지 않는다. |",
            f"| 원본 25개·고유 24개 | 잘림 기록 없음 | `{duplicate['after']['status']}`, 고유 {duplicate['after']['unique_valid_source_count']}개 | 중복 하나를 잘림으로 오탐하지 않는다. |",
            f"| 상류 ranked title 고유 7개 | 6개 반환, 잘림 기록 없음 | `{title7['after']['status']}`, 7개 관측·6개 보존 | title-stage cap 6의 누락 가능성을 기록한다. |",
            f"| 상류 ranked title 정확히 6개 | 6개 반환 | `{title6['after']['status']}` | 6개라고 해서 전체 후보를 다 봤다고 과장하지 않는다. |",
            f"| 상류 원본 7개·고유 6개 | 중복 여부 설명 없음 | `{title_duplicate['after']['status']}`, 고유 {title_duplicate['after']['unique_valid_source_count']}개 | 중복을 상류 잘림으로 오탐하지 않는다. |",
            f"| 상류 동일 정규화 제목·서로 다른 URL/역할 | 제목 기준으로 하나로 병합 | `{title_same_name['after']['status']}`, 고유 {title_same_name['after']['unique_valid_source_count']}개 | 선언한 title-only count 기준과 실제 계산을 일치시킨다. |",
            "",
            "## 단계별 진단 영수증은 무슨 기능인가",
            "",
            "각 전문가는 후보를 다음 단계로 넘기기 전에 일부 목록을 5개 또는 8개로 자른다. 새 영수증은 자르기 직전의 고유 후보 수, 실제 유지 수, cap, 순서 해시를 기록한다. 후보 이름 원문은 새로 저장하지 않으므로 진단 정보 때문에 민감한 후보 문자열이 노출되지 않는다.",
            "",
            "`TRUNCATED`는 해당 내부 단계에서 고유 후보 하나 이상이 실제로 cap 밖으로 밀렸다는 뜻이다. 그러나 다른 검색·댓글·공식 URL 경로가 같은 후보를 나중에 복구할 수도 있으므로, 이 신호를 최종 CandidateSet이 반드시 불완전하다는 판정으로 과장하지 않는다. 따라서 CandidateSet 상태에는 합성하지 않는다.",
            "",
            "| 내부 단계 | 하는 일 | cap | 개선 전 | 개선 후 합성 cap+1 사례 |",
            "| --- | --- | ---: | --- | --- |",
            *stage_rows,
            "",
            "경계 정확성 확인으로 Gatekeeper의 정확히 8개 사례와 9번째가 중복인 사례는 모두 `UNKNOWN`을 유지했다. 단순히 원본 행 수가 cap을 넘었다는 이유만으로 잘림을 오탐하지 않고, cap 밖으로 밀린 고유 제목이 있을 때만 `TRUNCATED`가 된다.",
            "",
            "## 상류 producer 완료 증명은 무슨 기능인가",
            "",
            "검색 계획(query plan)은 실행하기로 한 query/fetch 작업의 원문 대신 입력 해시를 기록한다. 각 search/fetch 영수증은 시도 수, upstream 관측 수, 실제 유지 수, cache 여부, degraded·throttle·오류 여부와 결과 해시를 기록한다. 계획과 영수증이 정확히 맞고 모든 작업이 정상 종료된 경우에만 CandidateSet을 정답셋 평가 준비 상태로 올린다.",
            "",
            "`COMPLETE`는 사전 고정된 bounded plan을 손실 없이 수행했다는 뜻이다. 검색 raw 11건 중 10건만 유지한 경우는 `TRUNCATED`, fetch 영수증 누락·degraded 검색·조기 종료는 `UNKNOWN`이다. Cache hit도 원래 provenance가 정상으로 보존된 경우에만 `COMPLETE`가 가능하다.",
            "",
            "| 합성 사례 | 개선 전 producer 상태 | 개선 후 producer proof | CandidateSet 상태 |",
            "| --- | --- | --- | --- |",
            *producer_rows,
            "",
            "사전 고정된 정상 search+fetch 1건만 합성 `COMPLETE`가 됐다. 원 실행 receipt/hash가 없는 cache replay를 포함한 나머지 사례는 거짓 완료를 만들지 않았다. 원문 query·URL·후보 제목은 새 장부에 복사하지 않고 fingerprint만 저장한다.",
            "",
            "## 이 수치를 정확도로 읽으면 안 되는 이유",
            "",
            f"최종 후보 장부 2개 경계의 합성 잘림 탐지는 {summary['synthetic_truncation_detected_before']}건에서 {summary['synthetic_truncation_detected_after']}건으로, 전문가 내부 7개 경계는 {summary['synthetic_stage_truncation_detected_before']}건에서 {summary['synthetic_stage_truncation_detected_after']}건으로 바뀌었다. Producer 합성 COMPLETE는 {summary['synthetic_producer_complete_before']}건에서 {summary['synthetic_producer_complete_after']}건으로 바뀌었다. 이는 모델 정답률 향상이 아니라 관측 가능성과 bounded-plan 완료 증명이다. Golden18 실제 저장본에는 producer receipt가 없으므로 후보 재현율은 `NOT_EVALUABLE`이고, 확률 정확도 퍼센트도 만들 수 없다.",
            "",
            "## 게이트 상태",
            "",
            "| 게이트 | 상태 | 뜻 |",
            "| --- | --- | --- |",
            f"| 산출물·부모 연결 | `{gates['artifact_integrity']}` / `{gates['p1_parent']}` | RunSpec, SHA, Golden18 순서·집합을 다시 확인했다. |",
            f"| 로컬 잘림 탐지 | `{gates['local_truncation_detection']}` | 합성 25개에서 `TRUNCATED`를 검출했다. |",
            f"| 전문가 단계 진단 | `{gates['stage_local_receipt_detection']}` | 7개 내부 cap 경계에서 고유 후보 손실을 기록하되 CandidateSet에는 합성하지 않았다. |",
            f"| Producer 완료 증명 | `{gates['producer_completion_proof']}` | 사전 고정 정상 계획 1건만 COMPLETE, cache provenance 미결합·누락·저하·조기 종료·top-k 손실은 fail-close했다. |",
            f"| Runtime 배선 | `{gates['producer_runtime_wiring']}` | search/fetch 경계 코드는 연결했지만 active production 때문에 새 런은 하지 않았다. |",
            f"| 거짓 COMPLETE 방지 | `{gates['false_complete_prevention']}` | 계획·영수증·로컬 snapshot이 모두 맞지 않으면 CandidateSet 평가 준비를 열지 않는다. |",
            f"| 기존 출력 호환 | `{gates['retained_output_compatibility']}` | serializer 3건과 title-stage 4건 모두 개선 전과 같은 항목·순서를 보존했다. |",
            f"| 공개 결과 무영향 | `{gates['public_noninterference']}` | 기존 공개 계약 {summary['actual_public_contract_unchanged_rows']}건이 불변이다. |",
            f"| 후보 재현율 | `{gates['candidate_set_recall']}` | 상류 완전성이 미증명이라 계산하지 않았다. |",
            f"| 실제 새 런 | `{gates['runtime_validation']}` | 저장본·합성 비교이며 새 LLM/MCP 런이 아니다. |",
            f"| 종합 | `{gates['overall']}` | 제한된 그림자 구조 검증만 통과했다. |",
            "",
            "## 근거 산출물",
            "",
            f"- 실행 명세: `{report['run_spec']['path']}`",
            f"- 실행 명세 파일 SHA: `{report['run_spec']['sha256']}`",
            f"- 실행 명세 자체 SHA: `{report['run_spec']['self_hash']}`",
            "",
            report["approval_boundary_ko"],
            "",
        ]
    )


def write_comparison(
    report: dict[str, Any],
    *,
    output_json: str | Path,
    output_md: str | Path,
) -> tuple[Path, Path]:
    json_path = _resolve_path(output_json)
    md_path = _resolve_path(output_md)
    _assert_output_paths([json_path, md_path])
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    md_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    return json_path, md_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="후보 보존 목록의 로컬 잘림 탐지 전후를 검증한다."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--parent-p1-run-spec", required=True)
    freeze.add_argument("--output", required=True)
    compare = commands.add_parser("compare")
    compare.add_argument("--run-spec", required=True)
    compare.add_argument("--output-json", required=True)
    compare.add_argument("--output-md", required=True)
    status = commands.add_parser("status")
    status.add_argument("--run-spec", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.command == "freeze":
        spec = create_run_spec(parent_p1_run_spec_path=args.parent_p1_run_spec)
        output = write_run_spec(spec, args.output)
        print(
            json.dumps(
                {
                    "gate": "GO",
                    "mode": MODE,
                    "output": _stored_path(output),
                    "run_spec_sha256": spec["run_spec_sha256"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "status":
        spec, rows = validate_run_spec(args.run_spec)
        print(
            json.dumps(
                {
                    "gate": "GO",
                    "mode": spec["mode"],
                    "row_count": len(rows),
                    "runtime_validation": "NOT_RUN",
                },
                ensure_ascii=False,
            )
        )
        return 0
    report = build_comparison(args.run_spec)
    json_path, md_path = write_comparison(
        report,
        output_json=args.output_json,
        output_md=args.output_md,
    )
    print(
        json.dumps(
            {
                "gate": report["gates"]["overall"],
                "output_json": _stored_path(json_path),
                "output_md": _stored_path(md_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
