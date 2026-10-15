"""과거 저장본에 의존하지 않는 합성 18행 P0/P1/producer/P2/P3 그래프.

모든 런/건강/라벨 필드는 계약 시험용이며 실제 모델·서비스 관측이 아니다.
validator나 지문 검사를 mock하지 않고 현재 builder와 raw byte 참조를 사용한다.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from src.llm_batch.promotion_gate import (
    EvidenceRecord, GroundingState, ScopeState, apply_publish_contract,
    evaluate_publish_contract,
)
from tools import run_pipeline_improvement_harness as p0
from tools import run_candidate_set_nil_shadow_harness as p1
from tools import run_candidate_generation_completeness_harness as producer
from tools import run_publication_exact_once_harness as p2
from tools import run_candidate_set_calibration_shadow_harness as p3
from tools import run_calibration_dataset_readiness as readiness_tool


def new_graph_directory() -> TemporaryDirectory:
    # P2 제품 writer의 원래 경로 제한을 그대로 따른다.
    p2.OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    return TemporaryDirectory(prefix="r4_synthetic_fixture_", dir=p2.OUTPUT_ROOT)


def write_json(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def artifact_ref(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": path.resolve().relative_to(p0.ROOT).as_posix(),
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def synthetic_row(index: int) -> dict:
    post_id = 840000 + index
    title = f"R4 합성 작품 {index}" if index <= 9 else ""
    publish = index <= 3
    url = f"https://example.test/r4-synthetic/{post_id}" if title else ""
    state = GroundingState(
        post_id=post_id, candidate_title=title, candidate_url=url,
        source="r4_synthetic_contract_only", official_title_exists=bool(title),
        row_discusses_work_as_work=publish,
        title_resolution_state="resolved" if publish else "unresolved_matchable",
        work_resolution="resolved" if publish else "unresolved",
        discussion_type="specific_work" if publish else "unknown",
        scope=ScopeState(scope_kind="current_work" if publish else "unknown",
                         confidence="high" if publish else "low",
                         direct_bridge_sources=("body", "official_detail") if publish else (),
                         conflict_reason_codes=() if publish else ("synthetic_hold",)),
    )
    evidence = [EvidenceRecord(kind="official_detail" if publish else "synthetic_hold",
                               strength="strong", source_path_or_snippet=url,
                               supports_publish=publish, reason_code="synthetic_contract_only",
                               candidate_title=title, candidate_url=url)] if title else []
    identity = {}
    apply_publish_contract(identity, evaluate_publish_contract(state, evidence))
    assert identity["promotion_decision"]["publish_allowed"] is publish
    return {"post_id": post_id, "title": f"R4 합성 입력 {index}",
            "analysis_result": {"identity": identity},
            "run_meta": {"runtime_release_fingerprint_sha256": "4" * 64,
                         "run_id": "r4-synthetic-contract-only", "model": "synthetic-no-model",
                         "llm_endpoint": "https://example.invalid/no-call",
                         "prompt_version": "synthetic-contract-v1", "config_hash": "5" * 64,
                         "requested_parallel": 16, "effective_parallel": 16,
                         "mcp_health_include_search": True, "mcp_health_light_mode": False}}


def build_current_shadow_graph(root: Path, *, include_calibration: bool = True) -> SimpleNamespace:
    root = root.resolve()
    if p2.OUTPUT_ROOT.resolve() not in root.parents:
        raise ValueError("synthetic graph must stay inside the existing P2 output boundary")
    paths = {key: root / rel for key, rel in {
        "input": "source/input.json", "baseline": "source/result.json",
        "manifest": "source/manifest.json", "plan": "source/runtime_plan.json",
        "integrity": "source/integrity.json", "gate": "source/retrieval_gate.json",
        "audit": "source/audit.json", "ledger": "source/ledger.json",
        "p0": "p0/run_spec.json", "p1": "p1/run_spec.json",
        "p1_comparison": "p1/comparison.json", "producer": "producer/run_spec.json",
        "p2": "p2/run_spec.json", "p2_comparison": "p2/comparison.json",
        "readiness": "readiness/readiness.json", "p3": "p3/run_spec.json",
        "p3_comparison": "p3/comparison.json",
    }.items()}
    rows = [synthetic_row(index) for index in range(1, 19)]
    meta = rows[0]["run_meta"]
    write_json(paths["input"], [{"post_id": row["post_id"], "title": row["title"]} for row in rows])
    write_json(paths["baseline"], rows)
    manifest = {"run_id": meta["run_id"], "runtime_release_fingerprint_sha256": "4" * 64,
                "input_post_count": 18, "completed_count": 18, "flushed_count": 18,
                "pending_count": 0, "failed_count": 0, "large_run_complete": True,
                "requested_parallel": 16, "effective_parallel": 16,
                "llm_model": meta["model"], "llm_endpoint": meta["llm_endpoint"],
                "dashboard_enabled": True, "mcp_health_include_search": True,
                "mcp_health_light_mode": False, "vlm_enabled": True, "ocr_enabled": True}
    write_json(paths["manifest"], manifest)
    write_json(paths["plan"], {
        "runtime_release_fingerprint_sha256": "4" * 64,
        "source_input": artifact_ref(paths["input"]),
        "output_contract": {"output_json": str(paths["baseline"]), "manifest_json": str(paths["manifest"])},
        "runtime_contract": {"model": meta["model"], "endpoint": meta["llm_endpoint"],
                             "prompt_version": meta["prompt_version"], "requested_parallel": 16,
                             "effective_parallel_expected": 16, "dashboard_required": True,
                             "search_include": True, "search_light_mode": False,
                             "slang_db": "off", "vlm": "on", "ocr": "on"}})
    write_json(paths["integrity"], {
        "runtime_integrity_gate": "GO", "run_id": meta["run_id"],
        "runtime_release_fingerprint_sha256": "4" * 64,
        "counts": {"input": 18, "result": 18, "checkpoint": 18, "pending": 0,
                   "failed": 0, "missing": 0, "extra": 0, "duplicate": 0},
        "runtime_contract": {"model": meta["model"], "requested_parallel": 16, "effective_parallel": 16,
                             "dashboard_enabled": True, "search_include": True, "search_light_mode": False,
                             "healthy_shards": "16/16", "slang_db_requested": "off",
                             "vlm_enabled": True, "ocr_enabled": True, "vlm_ocr_ready": True},
        "artifact_sha256": {key: artifact_ref(paths[name])["sha256"] for key, name in
                            (("input", "input"), ("result", "baseline"), ("manifest", "manifest"))}})
    write_json(paths["gate"], {"gate": "GO", "row_count": 18, "required_search_hard_blocker": 0,
                              "required_search_hard_blocker_rows": [], "artifact_provenance": {
                                  "result": artifact_ref(paths["baseline"]), "manifest": artifact_ref(paths["manifest"])}})
    spec0 = p0.create_run_spec(input_path=paths["input"], baseline_path=paths["baseline"],
        baseline_manifest_path=paths["manifest"], runtime_plan_path=paths["plan"],
        integrity_artifact_path=paths["integrity"], retrieval_gate_path=paths["gate"])
    p0.write_run_spec(spec0, paths["p0"])
    p0.validate_run_spec(paths["p0"])
    audit_rows, labels = [], []
    for index, row in enumerate(rows, 1):
        title = f"R4 합성 작품 {index}" if index <= 9 else None
        audit_row = {"post_id": row["post_id"], "passed": True}
        label = {"post_id": row["post_id"], "truth_kind": "CANDIDATE" if index <= 9 else "NIL" if index <= 15 else "UNJUDGED", "expected_title": title}
        if index <= 9:
            audit_row.update(golden_role="positive_expected_work", expected_title_or_hypothesis=title)
        elif index <= 15:
            audit_row.update(golden_role="negative_no_public_work", expected_no_public_title=True, status="expected_null_respected")
        else:
            label["expected_action"] = "ABSTAIN"
        audit_rows.append(audit_row)
        labels.append(label)
    contract = spec0["post_contract"]
    write_json(paths["audit"], {"report_type": "golden18_bound_audit", "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False, "row_count": 18, "after_result_sha256": artifact_ref(paths["baseline"])["sha256"],
        "after_post_id_order_sha256": contract["post_id_order_sha256"],
        "after_post_id_set_sha256": contract["post_id_set_sha256"], "rows": audit_rows})
    write_json(paths["ledger"], {"schema_version": "candidate-set-nil-label-ledger-v1",
        "source_expected_audit": artifact_ref(paths["audit"]), "source_baseline_result": artifact_ref(paths["baseline"]),
        "label_policy": {"abstain_is_not_truth_label": True, "candidate_set_recall_requires_complete_generation_status": True},
        "semantic_quality": "REVIEW-LOCKED", "full_scan_approval": False,
        "counts": {"rows": 18, "candidate_truth": 9, "nil_truth": 6, "unjudged": 3}, "rows": labels})
    spec1 = p1.create_run_spec(parent_p0_run_spec_path=paths["p0"], expected_audit_path=paths["audit"], label_ledger_path=paths["ledger"])
    p1.write_run_spec(spec1, paths["p1"])
    p1.validate_run_spec(paths["p1"])
    write_json(paths["p1_comparison"], p1.build_saved_artifact_comparison(paths["p1"]))
    producer_spec = producer.create_run_spec(parent_p1_run_spec_path=paths["p1"])
    producer.write_run_spec(producer_spec, paths["producer"])
    producer.validate_run_spec(paths["producer"])
    spec2 = p2.create_run_spec(parent_p1_run_spec_path=paths["p1"], parent_producer_run_spec_path=paths["producer"])
    p2.write_run_spec(spec2, paths["p2"])
    p2.validate_run_spec(paths["p2"])
    write_json(paths["p2_comparison"], p2.build_comparison(paths["p2"]))
    if include_calibration:
        ready = readiness_tool.build_current_readiness(p1_run_spec_path=paths["p1"],
            p1_comparison_path=paths["p1_comparison"], label_ledger_path=paths["ledger"])
        write_json(paths["readiness"], ready)
        spec3 = p3.create_run_spec(parent_p1_run_spec_path=paths["p1"], parent_p1_comparison_path=paths["p1_comparison"],
            parent_p2_run_spec_path=paths["p2"], parent_p2_comparison_path=paths["p2_comparison"],
            label_ledger_path=paths["ledger"], dataset_readiness_path=paths["readiness"])
        p3.write_run_spec(spec3, paths["p3"])
        p3.validate_run_spec(paths["p3"])
        write_json(paths["p3_comparison"], p3.build_comparison(paths["p3"]))
    write_json(root / "fixture_manifest.json", {"schema_version": "r4_synthetic_shadow_graph_v1",
        "evidence_scope": "SYNTHETIC_CONTRACT_ONLY", "model_calls": 0, "service_health_observed": False,
        "copied_historical_rows": False, "source_validation_mocks": False,
        "artifacts": {key: artifact_ref(path) for key, path in paths.items() if path.is_file()}})
    return SimpleNamespace(root=root, **paths)
