import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.llm_batch.promotion_gate import (
    apply_publish_contract,
    candidate_inventory_evidence_from_sources,
    evaluate_publish_contract,
    evidence_records_from_payload,
    grounding_state_from_dict,
)

from tools.safe_loss_flip_rate_probe import (
    _blind_judge_binding,
    analyze_flip_rate,
    audit_run_plan_runtime_contract,
    build_independent_run_plan,
    build_probe_input,
    load_blind_judge,
    load_rows,
    row_outcome,
    write_probe_input,
)
from tools.build_promotion_contract_n5_blind_judge import (
    EXPECTED_POST_IDS as _N5_EXPECTED_POST_IDS,
    build_judge as _build_n5_judge,
)
from tools.run_independent_plan import (
    _adoption_receipt_payload,
    _attempt_claim_payload,
    _attempt_file_paths,
    _child_started_path,
    _child_started_receipt_payload,
    _execution_claim_contract,
    _ensure_runtime_path_claims,
    _file_sha256 as _runner_file_sha256,
    _plan_claim_payload,
    _planned_runtime_path_entries,
    _resolve_path as _runner_resolve_path,
    _run_artifact_paths,
    _run_execution_paths,
    _terminal_receipt_payload,
    _validate_complete_run_artifacts,
)


def _input_row(post_id):
    return {"post_id": post_id, "title": f"title-{post_id}", "content": ["same"]}


def _result_row(post_id, status, title="작품", url="https://novelpia.com/novel/1"):
    return {
        "post_id": post_id,
        "analysis_result": {
            "identity": {
                "candidate_ledger_status": status,
                "novel_identity": {
                    "official_title": title if status == "safe_resolved" else None,
                    "heretic_url": url if status == "safe_resolved" else None,
                },
                "blocked_official_title": title if status != "safe_resolved" else None,
                "blocked_official_title_url": url if status != "safe_resolved" else None,
            }
        },
    }


_CANONICAL_CONTRACT_VALUE = object()


def _contract_result_row(
    post_id,
    *,
    public_title=None,
    public_url=None,
    candidate_title=None,
    candidate_url=None,
    decision_status="publish",
    publish_allowed=True,
    candidate_preserved=False,
    bypassed_gate=False,
    reason_codes=None,
    scope_kind="current_work",
    direct_bridge_sources=None,
    promotion_evidence=None,
    candidate_inventory_sources=None,
    contract_version=_CANONICAL_CONTRACT_VALUE,
    input_fingerprint=_CANONICAL_CONTRACT_VALUE,
):
    reason_codes = list(reason_codes or [])
    required_runtime_reasons = (
        ["scope_current_work", "row_discusses_work_as_work", "serialized_public_identity_published"]
        if publish_allowed
        else [
            "scope_unknown" if scope_kind == "unknown" else f"scope_{scope_kind}",
            "scope_not_current_work",
            "serialized_public_identity_scrubbed",
        ]
    )
    for reason_code in required_runtime_reasons:
        if reason_code not in reason_codes:
            reason_codes.append(reason_code)
    state_candidate_title = candidate_title or public_title
    state_candidate_url = candidate_url or public_url
    direct_sources = list(direct_bridge_sources or [])
    if publish_allowed and not direct_sources:
        direct_sources = ["test_direct_bridge"]
    inventory_sources = copy.deepcopy(list(candidate_inventory_sources or []))
    evidence = copy.deepcopy(list(promotion_evidence or []))
    inventory_evidence = candidate_inventory_evidence_from_sources(inventory_sources)
    evidence.extend(record.to_dict() for record in inventory_evidence)
    qualifying_evidence = any(
        item.get("supports_publish") is True
        and (not item.get("candidate_title") or item.get("candidate_title") == state_candidate_title)
        and (not item.get("candidate_url") or item.get("candidate_url") == state_candidate_url)
        and item.get("title_url_match") is not False
        for item in evidence
        if isinstance(item, dict)
    )
    if publish_allowed and not qualifying_evidence:
        evidence.append(
            {
                "kind": "test_publish_support",
                "strength": "high",
                "supports_publish": True,
                "reason_code": "test_publish_support",
                "candidate_title": state_candidate_title,
                "candidate_url": state_candidate_url,
                "title_url_match": True if state_candidate_url else None,
            }
        )
    state_payload = {
        "post_id": post_id,
        "candidate_title": state_candidate_title,
        "candidate_url": state_candidate_url,
        "source": "safe_loss_contract_test",
        "official_title_exists": bool(state_candidate_title),
        "row_discusses_work_as_work": scope_kind == "current_work",
        "title_resolution_state": "resolved" if publish_allowed else "unresolved_matchable",
        "work_resolution": "resolved" if publish_allowed else "unresolved",
        "discussion_type": "review",
        "scope": {
            "scope_kind": scope_kind,
            "confidence": "high",
            "direct_bridge_sources": direct_sources,
            "competing_candidates": [],
            "conflict_reason_codes": reason_codes,
        },
        "candidate_inventory_count": len(inventory_evidence),
    }
    contract = evaluate_publish_contract(
        grounding_state_from_dict(state_payload),
        evidence_records_from_payload(evidence),
        post_gate_context={
            "title_resolution_allowed": publish_allowed,
            "title_resolution_state": "resolved" if publish_allowed else "unresolved_matchable",
            "work_resolution": "resolved" if publish_allowed else "unresolved",
        },
    )
    self_decision = contract.decision
    if self_decision.publish_allowed != publish_allowed:
        raise AssertionError(
            f"fixture publish_allowed mismatch: expected={publish_allowed} actual={self_decision.publish_allowed}"
        )
    if self_decision.status != decision_status:
        raise AssertionError(
            f"fixture decision status mismatch: expected={decision_status} actual={self_decision.status}"
        )
    if self_decision.candidate_preserved != candidate_preserved:
        raise AssertionError(
            "fixture candidate_preserved mismatch: "
            f"expected={candidate_preserved} actual={self_decision.candidate_preserved}"
        )
    identity = {
        "novel_identity": {
            "official_title": None,
            "heretic_url": None,
        },
    }
    apply_publish_contract(identity, contract)
    if inventory_sources:
        identity["title_candidates"] = copy.deepcopy(inventory_sources)
        identity["candidate_preservation_sources"] = copy.deepcopy(inventory_sources)

    decision_surfaces = [
        identity["promotion_decision"],
        identity["publish_contract_trace"]["gate_decision"],
        identity["publish_ledger"]["gate_decision"],
        identity["candidate_ledger"]["promotion_decision"],
        identity["candidate_ledger"]["publish_contract_trace"]["gate_decision"],
        identity["candidate_ledger"]["publish_ledger"]["gate_decision"],
    ]
    trace_surfaces = [
        identity["publish_contract_trace"],
        identity["candidate_ledger"]["publish_contract_trace"],
    ]
    if bypassed_gate:
        for surface in decision_surfaces:
            surface["bypassed_gate"] = True
        for surface in trace_surfaces:
            surface["bypassed_gate"] = True

    def override_contract_field(field, value):
        for surface in decision_surfaces:
            if value is None:
                surface.pop(field, None)
            else:
                surface[field] = value
        for surface in trace_surfaces:
            if value is None:
                surface.pop(field, None)
            else:
                surface[field] = value
        top_field = (
            "publish_contract_input_fingerprint"
            if field == "input_fingerprint"
            else "publish_contract_version"
        )
        for owner in (identity, identity["candidate_ledger"]):
            if value is None:
                owner.pop(top_field, None)
            else:
                owner[top_field] = value

    if input_fingerprint is not _CANONICAL_CONTRACT_VALUE:
        override_contract_field("input_fingerprint", input_fingerprint)
    if contract_version is not _CANONICAL_CONTRACT_VALUE:
        override_contract_field("contract_version", contract_version)

    if not publish_allowed and public_title is not None:
        identity["novel_identity"]["official_title"] = public_title
        identity["novel_identity"]["heretic_url"] = public_url
    return {"post_id": post_id, "analysis_result": {"identity": identity}}


def _repeat(row, count=5):
    rows = []
    for index in range(count):
        repeated = copy.deepcopy(row)
        repeated["_flip_probe_result_binding"] = {"test_repeat_index": index}
        unwrapped = repeated.get("result") if isinstance(repeated.get("result"), dict) else repeated
        unwrapped["run_meta"] = {
            "run_id": f"test-independent-run-{index}",
            "model": "test-gemma",
            "llm_mode": "remote",
            "llm_endpoint": "http://127.0.0.1:8000",
            "prompt_version": "test-prompt-v1",
            "config_hash": "test-config-v1",
            "runtime_release_fingerprint_sha256": "a" * 64,
        }
        rows.append(repeated)
    return rows


def _acceptable_outcome(
    *,
    public_title,
    public_url,
    candidate_title,
    candidate_url,
    decision_status,
    publish_allowed,
    candidate_preserved,
    bypassed_gate=False,
    scope_kind="current_work",
    required_reason_codes=None,
    required_direct_bridge_sources=None,
    required_evidence_kinds=None,
    required_evidence_reason_codes=None,
    required_publish_supporting_evidence_kinds=None,
    required_publish_supporting_evidence_reason_codes=None,
    required_candidate_inventory_pairs=None,
    require_fingerprint=True,
    require_contract_version="promotion_contract_v2",
):
    outcome = {
        "public_title": public_title,
        "public_url": public_url,
        "candidate_title": candidate_title,
        "candidate_url": candidate_url,
        "decision_status": decision_status,
        "publish_allowed": publish_allowed,
        "candidate_preserved": candidate_preserved,
        "bypassed_gate": bypassed_gate,
        "scope_kind": scope_kind,
        "required_reason_codes": list(required_reason_codes or []),
        "required_direct_bridge_sources": list(required_direct_bridge_sources or []),
        "required_evidence_kinds": list(required_evidence_kinds or []),
        "required_evidence_reason_codes": list(required_evidence_reason_codes or []),
        "required_publish_supporting_evidence_kinds": list(
            required_publish_supporting_evidence_kinds
            if required_publish_supporting_evidence_kinds is not None
            else required_evidence_kinds or []
        ),
        "required_publish_supporting_evidence_reason_codes": list(
            required_publish_supporting_evidence_reason_codes
            if required_publish_supporting_evidence_reason_codes is not None
            else required_evidence_reason_codes or []
        ),
        "require_fingerprint": require_fingerprint,
        "require_contract_version": require_contract_version,
    }
    if required_candidate_inventory_pairs is not None:
        outcome["required_candidate_inventory_pairs"] = copy.deepcopy(
            required_candidate_inventory_pairs
        )
    return outcome


_RUNTIME_AUDIT_POST_IDS = list(_N5_EXPECTED_POST_IDS)
_RUNTIME_AUDIT_CONTRACT = {
    "model": "test-gemma",
    "llm_mode": "remote",
    "llm_endpoint": "http://127.0.0.1:8000",
    "prompt_version": "test-prompt-v1",
    "config_hash": "test-config-v1",
    "runtime_release_fingerprint_sha256": "b" * 64,
}


def _test_file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_bound_blind_judge(root: Path, post_ids: list[str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parents[1]
    if tuple(post_ids) != tuple(_N5_EXPECTED_POST_IDS):
        raise AssertionError("bound blind judge fixture requires canonical N5 post_ids")
    payload = _build_n5_judge(
        source_manifest_path=(
            repo_root / "docs/devs/loop642_promotion_contract_n5_source_input_manifest.json"
        ),
        golden_manifest_path=(
            repo_root
            / "out/regression_safe_grounding_20260626_000008_928006_loop01/golden/golden_manifest.json"
        ),
        blind_adjudication_path=(
            repo_root / "docs/devs/loop641_merged375_adjusted_collateral_adjudication.json"
        ),
        independent_identity_evidence_path=(
            repo_root
            / "docs/devs/loop642_promotion_contract_n5_independent_identity_evidence_20260710.json"
        ),
        r6_golden_audit_path=(
            repo_root
            / "docs/devs/loop642_promotion_contract_golden18_r6_i5_expected_audit.json"
        ),
        r6_result_path=(
            repo_root
            / "out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop642_promotion_contract_golden18_r6_i5_result.json"
        ),
        generated_at="2026-07-10T00:00:00",
    )
    judge_path = root / "blind_judge.json"
    judge_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return judge_path


def _result_from_bound_judge_row(judge_row: dict) -> dict:
    """Materialize one real typed-contract result accepted by a judge row."""

    post_id = str(judge_row["post_id"])
    outcome = copy.deepcopy(judge_row["acceptable_outcomes"][0])
    required_kinds = list(outcome.get("required_evidence_kinds") or [])
    required_evidence_reasons = list(
        outcome.get("required_evidence_reason_codes") or []
    )
    supporting_kinds = set(
        outcome.get("required_publish_supporting_evidence_kinds") or []
    )
    supporting_reasons = set(
        outcome.get("required_publish_supporting_evidence_reason_codes") or []
    )
    evidence = []
    for index, kind in enumerate(required_kinds):
        reason_code = (
            required_evidence_reasons[index]
            if index < len(required_evidence_reasons)
            else kind
        )
        evidence.append(
            {
                "kind": kind,
                "strength": "strong",
                "supports_publish": bool(
                    kind in supporting_kinds or reason_code in supporting_reasons
                ),
                "reason_code": reason_code,
                "candidate_title": (
                    outcome.get("candidate_title") or outcome.get("public_title")
                ),
                "candidate_url": (
                    outcome.get("candidate_url") or outcome.get("public_url")
                ),
                "title_url_match": bool(
                    outcome.get("candidate_url") or outcome.get("public_url")
                ),
            }
        )
    inventory_sources = [
        {
            "official_title": pair.get("title"),
            "heretic_url": pair.get("url"),
        }
        for pair in (outcome.get("required_candidate_inventory_pairs") or [])
    ]
    return _contract_result_row(
        post_id,
        public_title=outcome.get("public_title"),
        public_url=outcome.get("public_url"),
        candidate_title=outcome.get("candidate_title"),
        candidate_url=outcome.get("candidate_url"),
        decision_status=outcome["decision_status"],
        publish_allowed=outcome["publish_allowed"],
        candidate_preserved=outcome["candidate_preserved"],
        bypassed_gate=outcome["bypassed_gate"],
        reason_codes=outcome.get("required_reason_codes"),
        scope_kind=outcome["scope_kind"],
        direct_bridge_sources=outcome.get("required_direct_bridge_sources"),
        promotion_evidence=evidence,
        candidate_inventory_sources=inventory_sources,
    )


def _write_runtime_plan_fixture(
    root: Path, *, first_search_health: dict | None = None
):
    root.mkdir(parents=True, exist_ok=True)
    plan_path = root / "run_plan.json"
    blind_judge_path = _write_bound_blind_judge(root, list(_RUNTIME_AUDIT_POST_IDS))
    analysis_output_json = root / "analysis.json"
    analysis_output_md = root / "analysis.md"
    plan, input_writes = build_independent_run_plan(
        source_rows=[_input_row(post_id) for post_id in _RUNTIME_AUDIT_POST_IDS],
        post_ids=list(_RUNTIME_AUDIT_POST_IDS),
        repeats=5,
        work_dir=root,
        run_prefix="runtime_audit",
        python_executable=sys.executable,
        expert_main=Path("expert_main.py"),
        parallel=16,
        runtime_model=_RUNTIME_AUDIT_CONTRACT["model"],
        runtime_llm_mode=_RUNTIME_AUDIT_CONTRACT["llm_mode"],
        runtime_llm_endpoint=_RUNTIME_AUDIT_CONTRACT["llm_endpoint"],
        runtime_prompt_version=_RUNTIME_AUDIT_CONTRACT["prompt_version"],
        runtime_release_fingerprint_sha256=_RUNTIME_AUDIT_CONTRACT[
            "runtime_release_fingerprint_sha256"
        ],
        required_env={"TEST_REQUIRED_ENV": "bound"},
        blind_judge=blind_judge_path,
        run_plan_path=plan_path,
        analysis_output_json=analysis_output_json,
        analysis_output_md=analysis_output_md,
    )
    for input_path, input_row in input_writes:
        write_probe_input([input_row], input_path)
    judge_payload = json.loads(blind_judge_path.read_text(encoding="utf-8"))
    judge_rows = {
        str(row["post_id"]): row
        for row in judge_payload["rows"]
    }
    results = []
    manifests = []
    for run in plan["planned_runs"]:
        repeat_index = run["repeat_index"]
        post_id = run["post_id"]
        result_path = Path(run["output_json"])
        manifest_path = Path(run["manifest_json"])
        checkpoint_path = Path(run["checkpoint_jsonl"])
        result_path.parent.mkdir(parents=True, exist_ok=True)
        run_id = f"runtime-audit-{post_id}-r{repeat_index:02d}"
        row = _result_from_bound_judge_row(judge_rows[str(post_id)])
        row["run_meta"] = {
            "run_id": run_id,
            **_RUNTIME_AUDIT_CONTRACT,
            "requested_parallel": 16,
            "effective_parallel": 1,
            "search_health": {
                "status": "ok",
                "degraded": 0,
                "degraded_recovered": 0,
                "unrecovered_degraded": 0,
            },
        }
        if first_search_health is not None and not results:
            row["run_meta"]["search_health"] = copy.deepcopy(first_search_health)
        result_path.write_text(json.dumps([row], ensure_ascii=False), encoding="utf-8")
        checkpoint_path.write_text(
            json.dumps(
                {
                    "global_idx": 0,
                    "post_id": int(post_id),
                    "status": "completed",
                    "result": row,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        manifest = {
            "run_id": run_id,
            "output_file": str(result_path),
            "checkpoint_jsonl": str(checkpoint_path),
            "input_post_count": 1,
            "completed_count": 1,
            "flushed_count": 1,
            "pending_count": 0,
            "failed_count": 0,
            "requested_parallel": 16,
            "effective_parallel": 1,
            "dashboard_enabled": True,
            "dashboard_mode": "standalone_forward",
            "dashboard_standalone_forwarding": True,
            "dashboard_start_error": "",
            "mcp_health_include_search": True,
            "mcp_health_light_mode": False,
            "mcp_health_required_ok_count": 16,
            "mcp_health_checked_endpoint_count": 16,
            "mcp_health_ok_count": 16,
            "mcp_health_failure_count": 0,
            "mcp_requested_endpoint_count_before_health_filter": 16,
            "mcp_healthy_endpoint_count": 16,
            "mcp_endpoint_count_after_health_filter": 16,
            "vlm_enabled": True,
            "ocr_enabled": True,
            "vlm_ocr_semantic_review_ready": True,
            "vlm_ocr_semantic_review_required_for_images": True,
            "vlm_ocr_semantic_review_skip_reasons": [],
            "vlm_ocr_semantic_review_skip_reason": "",
            "vlm_ocr_semantic_review_blocker": False,
            "vlm_ocr_semantic_review_blocker_code": "",
            "vlm_ocr_semantic_review_blocker_action": "",
            "partial_flush_gap": False,
            "ordered_flush_blocked": False,
            "llm_model": _RUNTIME_AUDIT_CONTRACT["model"],
            "llm_endpoint": _RUNTIME_AUDIT_CONTRACT["llm_endpoint"],
            "runtime_release_fingerprint_sha256": _RUNTIME_AUDIT_CONTRACT[
                "runtime_release_fingerprint_sha256"
            ],
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        results.append(result_path)
        manifests.append(manifest_path)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    _materialize_runtime_execution_provenance(plan_path, plan)
    return plan_path, results, manifests, blind_judge_path


def _materialize_runtime_execution_provenance(plan_path: Path, plan: dict) -> None:
    runs = plan["planned_runs"]
    contract = _execution_claim_contract(plan_path=plan_path, plan=plan, runs=runs)
    global_claim_path = _runner_resolve_path(contract["persistent_plan_claim_json"])
    global_claim = _plan_claim_payload(
        plan_path=plan_path,
        plan=plan,
        runs=runs,
        contract=contract,
    )
    global_claim_path.parent.mkdir(parents=True, exist_ok=True)
    global_claim_path.write_text(
        json.dumps(global_claim, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _ensure_runtime_path_claims(
        _planned_runtime_path_entries(runs), plan_claim=global_claim
    )
    global_claim_sha256 = _runner_file_sha256(global_claim_path)
    for index, run in enumerate(runs, start=1):
        artifact_paths = _run_artifact_paths(run, index=index)
        execution_paths = _run_execution_paths(contract=contract, run=run, index=index)
        claim_path, terminal_path = _attempt_file_paths(execution_paths["attempt_dir"], 1)
        claim = _attempt_claim_payload(
            run=run,
            index=index,
            attempt_index=1,
            plan_sha256=global_claim["plan_sha256"],
            global_claim_sha256=global_claim_sha256,
            artifact_paths=artifact_paths,
        )
        claim_path.parent.mkdir(parents=True, exist_ok=True)
        claim_path.write_text(
            json.dumps(claim, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        child_path = _child_started_path(execution_paths["attempt_dir"], 1)
        child = _child_started_receipt_payload(
            claim_path=claim_path,
            claim=claim,
            child_pid=100000 + index,
            process_creation_token=f"test-process-token-{index}",
        )
        child_path.write_text(
            json.dumps(child, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        artifact_binding = _validate_complete_run_artifacts(
            run, index=index, paths=artifact_paths
        )
        terminal = _terminal_receipt_payload(
            status="COMPLETE_VERIFIED",
            claim_path=claim_path,
            claim=claim,
            child_started_path=child_path,
            child_started=child,
            child_returncode=0,
            artifact_presence={field: True for field in artifact_paths},
            artifact_binding=artifact_binding,
        )
        terminal_path.write_text(
            json.dumps(terminal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        adoption = _adoption_receipt_payload(
            terminal_path=terminal_path,
            terminal=terminal,
        )
        adoption_path = execution_paths["adoption_receipt"]
        adoption_path.parent.mkdir(parents=True, exist_ok=True)
        adoption_path.write_text(
            json.dumps(adoption, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


class SafeLossFlipRateProbeTest(unittest.TestCase):
    def test_direct_script_entrypoint_imports_repo_tools(self):
        completed = subprocess.run(
            [sys.executable, "tools/safe_loss_flip_rate_probe.py", "--help"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("usage:", completed.stdout.lower())

    def test_build_probe_input_duplicates_rows_without_metadata(self):
        rows, missing = build_probe_input(
            source_rows=[_input_row(11674712), _input_row(11660237)],
            post_ids=["11674712", "11660237"],
            repeats=3,
        )

        self.assertEqual(missing, [])
        self.assertEqual(len(rows), 6)
        self.assertEqual([row["post_id"] for row in rows], [11674712, 11660237] * 3)
        self.assertNotIn("_flip_probe", rows[0])

    def test_build_paths_reject_duplicate_requested_or_source_post_ids(self):
        with self.assertRaisesRegex(ValueError, "duplicate requested post_ids"):
            build_probe_input(
                source_rows=[_input_row(1)],
                post_ids=["1", "1"],
                repeats=5,
            )
        with self.assertRaisesRegex(ValueError, "duplicate source post_ids"):
            build_probe_input(
                source_rows=[_input_row(1), {**_input_row(1), "title": "conflict"}],
                post_ids=["1"],
                repeats=5,
            )
        with self.assertRaisesRegex(ValueError, "duplicate requested post_ids"):
            build_independent_run_plan(
                source_rows=[_input_row(1)],
                post_ids=["1", "1"],
                repeats=5,
                work_dir=Path("runs"),
                run_prefix="duplicate",
                python_executable="python",
                expert_main=Path("expert_main.py"),
            )
        with self.assertRaisesRegex(ValueError, "duplicate source post_ids"):
            build_independent_run_plan(
                source_rows=[_input_row(1), {**_input_row(1), "title": "conflict"}],
                post_ids=["1"],
                repeats=5,
                work_dir=Path("runs"),
                run_prefix="duplicate-source",
                python_executable="python",
                expert_main=Path("expert_main.py"),
            )

    def test_blind_judge_loader_rejects_duplicate_post_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "judge.json"
            path.write_text(
                json.dumps(
                    {
                        "rows": [
                            {"post_id": 1, "expected_status": "safe_resolved"},
                            {"post_id": 1, "expected_status": "promotion_blocked"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate blind judge post_id"):
                load_blind_judge(path)

    def test_analyze_flip_rate_marks_oscillation_as_unresolved_nondeterminism(self):
        report = analyze_flip_rate(
            result_rows=[
                _result_row(11660237, "safe_resolved", "테라포밍"),
                _result_row(11660237, "promotion_blocked", "테라포밍"),
                _result_row(11660237, "safe_resolved", "테라포밍"),
            ],
            post_ids=["11660237"],
            repeats=3,
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertTrue(report["summary"]["any_flip"])
        self.assertEqual(report["rows"][0]["classification"], "nondeterminism_unresolved")
        self.assertAlmostEqual(report["rows"][0]["flip_rate"], 1 / 3)
        self.assertFalse(report["hard_hold_relaxation_allowed"])

    def test_analyze_flip_rate_requires_blind_judge_before_hard_hold_relaxation(self):
        report = analyze_flip_rate(
            result_rows=[
                _result_row(11698880, "safe_resolved", "가챠 중독자의 퓨전펑크 생활"),
                _result_row(11698880, "safe_resolved", "가챠 중독자의 퓨전펑크 생활"),
            ],
            post_ids=["11698880"],
            repeats=2,
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["rows"][0]["classification"], "stable_unsafe_outcome")
        self.assertFalse(report["hard_hold_relaxation_allowed"])

    def test_legacy_expected_contract_remains_compatible_but_review_only(self):
        result = _result_row(11698880, "safe_resolved", "가챠 중독자의 퓨전펑크 생활")
        report = analyze_flip_rate(
            result_rows=_repeat(result),
            post_ids=["11698880"],
            repeats=5,
            blind_judge={
                "11698880": {
                    "expected_status": "safe_resolved",
                    "expected_title": "가챠 중독자의 퓨전펑크 생활",
                    "expected_url": "https://novelpia.com/novel/1",
                }
            },
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["rows"][0]["classification"], "stable_unsafe_outcome")
        self.assertTrue(report["rows"][0]["blind_judge_expected_match"])
        self.assertFalse(report["rows"][0]["expected_contract_authoritative"])
        self.assertFalse(report["hard_hold_relaxation_allowed"])

    def test_analyze_flip_rate_never_goes_below_five_repeats(self):
        result = _result_row(11698880, "safe_resolved", "가챠 중독자의 퓨전펑크 생활")
        report = analyze_flip_rate(
            result_rows=_repeat(result, 2),
            post_ids=["11698880"],
            repeats=2,
            blind_judge={
                "11698880": {
                    "expected_status": "safe_resolved",
                    "expected_title": "가챠 중독자의 퓨전펑크 생활",
                    "expected_url": "https://novelpia.com/novel/1",
                }
            },
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertFalse(report["minimum_repeats_contract_met"])
        self.assertTrue(report["rows"][0]["blind_judge_expected_match"])

    def test_semantic_surface_ignores_fingerprint_evidence_inventory_variance_but_judges_every_repeat(self):
        post_id = "11660237"
        title = "테라포밍"
        url = "https://novelpia.com/novel/61947"
        common_reason = "official_detail_url"
        common_bridge = "official_detail_url"
        common_evidence = {
            "kind": "official_detail_url",
            "reason_code": "official_detail_url",
            "supports_publish": True,
            "candidate_title": title,
            "candidate_url": url,
            "title_url_match": True,
        }
        visual_reason = "official_detail_bracket_visual_release_context"
        rows = []
        for index in range(5):
            has_visual = index == 1
            evidence = [common_evidence]
            if has_visual:
                evidence.append(
                    {
                        "kind": visual_reason,
                        "reason_code": visual_reason,
                        "supports_publish": True,
                        "candidate_title": title,
                        "candidate_url": url,
                        "title_url_match": True,
                    }
                )
            result = _contract_result_row(
                post_id,
                public_title=title,
                public_url=url,
                decision_status="publish",
                publish_allowed=True,
                candidate_preserved=False,
                reason_codes=[common_reason] + ([visual_reason] if has_visual else []),
                direct_bridge_sources=[common_bridge] + ([visual_reason] if has_visual else []),
                promotion_evidence=evidence,
                candidate_inventory_sources=[
                    {
                        "official_title": f"진단 후보 {index}",
                        "heretic_url": f"https://example.invalid/inventory/{index}",
                    }
                ],
            )
            repeated = _repeat(result, 1)[0]
            repeated["_flip_probe_result_binding"] = {"test_repeat_index": index}
            repeated["run_meta"]["run_id"] = f"test-independent-run-{index}"
            rows.append(repeated)

        common_expected = _acceptable_outcome(
            public_title=title,
            public_url=url,
            candidate_title=None,
            candidate_url=None,
            decision_status="publish",
            publish_allowed=True,
            candidate_preserved=False,
            scope_kind="current_work",
            required_reason_codes=[common_reason],
            required_direct_bridge_sources=[common_bridge],
            required_evidence_kinds=[common_reason],
            required_evidence_reason_codes=[common_reason],
        )
        diagnostic_only = analyze_flip_rate(
            result_rows=rows,
            post_ids=[post_id],
            repeats=5,
            blind_judge={post_id: {"acceptable_outcomes": [common_expected]}},
        )

        diagnostic_row = diagnostic_only["rows"][0]
        self.assertEqual(diagnostic_only["gate"], "GO")
        self.assertTrue(diagnostic_only["summary"]["any_raw_outcome_variance"])
        self.assertFalse(diagnostic_only["summary"]["any_semantic_flip"])
        self.assertGreater(diagnostic_row["raw_unique_outcome_count"], 1)
        self.assertEqual(diagnostic_row["semantic_unique_decision_surface_count"], 1)
        self.assertTrue(diagnostic_row["flipped"])
        self.assertFalse(diagnostic_row["semantic_flipped"])
        self.assertEqual(diagnostic_row["blind_judge_mismatch_repeat_count"], 0)

        visual_expected = _acceptable_outcome(
            public_title=title,
            public_url=url,
            candidate_title=None,
            candidate_url=None,
            decision_status="publish",
            publish_allowed=True,
            candidate_preserved=False,
            scope_kind="current_work",
            required_reason_codes=[visual_reason],
            required_direct_bridge_sources=[visual_reason],
            required_evidence_kinds=[visual_reason],
            required_evidence_reason_codes=[visual_reason],
        )
        mismatch = analyze_flip_rate(
            result_rows=rows,
            post_ids=[post_id],
            repeats=5,
            blind_judge={post_id: {"acceptable_outcomes": [visual_expected]}},
        )

        mismatch_row = mismatch["rows"][0]
        self.assertEqual(mismatch["gate"], "NO-GO")
        self.assertFalse(mismatch_row["decision_surface_flipped"])
        self.assertTrue(mismatch_row["semantic_flipped"])
        self.assertEqual(mismatch_row["blind_judge_match_repeat_count"], 1)
        self.assertEqual(mismatch_row["blind_judge_mismatch_repeat_count"], 4)
        self.assertEqual(mismatch_row["unsafe_repeat_count"], 0)
        self.assertEqual(mismatch_row["unsafe_or_blind_judge_mismatch_repeat_count"], 4)
        self.assertEqual(len(mismatch_row["repeat_contract_evaluations"]), 5)
        self.assertEqual(
            [item["blind_judge_match"] for item in mismatch_row["repeat_contract_evaluations"]],
            [False, True, False, False, False],
        )

    def test_multiple_authoritative_acceptable_outcomes_form_safe_union_not_failure(self):
        post_id = "77"
        title = "정답 작품"
        url = "https://novelpia.com/novel/77"
        publish = _contract_result_row(
            post_id,
            public_title=title,
            public_url=url,
            decision_status="publish",
            publish_allowed=True,
            candidate_preserved=False,
        )
        hold = _contract_result_row(
            post_id,
            candidate_title=title,
            candidate_url=url,
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            reason_codes=["scope_context_only"],
            scope_kind="context_only",
        )
        rows = []
        for index, result in enumerate((publish, hold, publish, hold, publish)):
            repeated = _repeat(result, 1)[0]
            repeated["_flip_probe_result_binding"] = {"test_repeat_index": index}
            repeated["run_meta"]["run_id"] = f"test-independent-run-{index}"
            rows.append(repeated)

        report = analyze_flip_rate(
            result_rows=rows,
            post_ids=[post_id],
            repeats=5,
            blind_judge={
                post_id: {
                    "acceptable_outcomes": [
                        _acceptable_outcome(
                            public_title=title,
                            public_url=url,
                            candidate_title=None,
                            candidate_url=None,
                            decision_status="publish",
                            publish_allowed=True,
                            candidate_preserved=False,
                            scope_kind="current_work",
                            required_reason_codes=["scope_current_work"],
                            required_direct_bridge_sources=["test_direct_bridge"],
                            required_evidence_kinds=["test_publish_support"],
                            required_evidence_reason_codes=["test_publish_support"],
                        ),
                        _acceptable_outcome(
                            public_title=None,
                            public_url=None,
                            candidate_title=title,
                            candidate_url=url,
                            decision_status="candidate_only",
                            publish_allowed=False,
                            candidate_preserved=True,
                            scope_kind="context_only",
                            required_reason_codes=["scope_context_only"],
                        ),
                    ]
                }
            },
        )

        row = report["rows"][0]
        self.assertEqual(report["gate"], "GO")
        self.assertTrue(row["decision_surface_flipped"])
        self.assertFalse(row["semantic_flipped"])
        self.assertEqual(row["semantic_unique_decision_surface_count"], 2)
        self.assertEqual(row["blind_judge_match_repeat_count"], 5)
        self.assertEqual(row["blind_judge_mismatch_repeat_count"], 0)
        self.assertEqual(row["unsafe_repeat_count"], 0)
        self.assertEqual(row["classification"], "authoritative_acceptable_outcome_union")
        self.assertEqual(row["matched_acceptable_outcome_indexes"], [0, 1])
        self.assertTrue(row["acceptable_outcome_union_authoritative"])
        self.assertEqual(
            [
                item["matched_acceptable_outcome_index"]
                for item in row["repeat_contract_evaluations"]
            ],
            [0, 1, 0, 1, 0],
        )

    def test_stable_wrong_publish_is_judged_per_repeat_and_stays_no_go(self):
        post_id = "11663514"
        wrong = _contract_result_row(
            post_id,
            public_title="올바른 슬라임 사용법",
            public_url="https://novelpia.com/novel/268424",
            decision_status="publish",
            publish_allowed=True,
            candidate_preserved=False,
        )
        expected = _acceptable_outcome(
            public_title="마탄 속의 제국",
            public_url="https://novel.munpia.com/486006",
            candidate_title=None,
            candidate_url=None,
            decision_status="publish",
            publish_allowed=True,
            candidate_preserved=False,
            scope_kind="current_work",
            required_reason_codes=["scope_current_work"],
            required_direct_bridge_sources=["test_direct_bridge"],
            required_evidence_kinds=["test_publish_support"],
            required_evidence_reason_codes=["test_publish_support"],
        )

        report = analyze_flip_rate(
            result_rows=_repeat(wrong),
            post_ids=[post_id],
            repeats=5,
            blind_judge={post_id: {"acceptable_outcomes": [expected]}},
        )

        row = report["rows"][0]
        self.assertEqual(report["gate"], "NO-GO")
        self.assertFalse(row["semantic_flipped"])
        self.assertEqual(row["blind_judge_mismatch_repeat_count"], 5)
        self.assertEqual(row["unsafe_repeat_count"], 0)
        self.assertEqual(row["wrong_or_unsafe_repeat_count"], 5)
        self.assertTrue(
            all(
                item["blind_judge_mismatch"]
                for item in row["repeat_contract_evaluations"]
            )
        )

    def test_publish_title_and_canonical_url_contract_path(self):
        title = "아카데미 생존 갤러리"
        url = "https://novelpia.com/novel/380218"
        result = _contract_result_row(
            11694035,
            public_title=title,
            public_url=url,
            decision_status="publish",
            publish_allowed=True,
            candidate_preserved=False,
            reason_codes=["scope_current_work", "serialized_public_identity_published"],
            direct_bridge_sources=["explicit_alias_relation", "official_detail_url"],
            promotion_evidence=[
                {
                    "kind": "alias_relation",
                    "reason_code": "verified_explicit_alias",
                    "supports_publish": True,
                    "candidate_title": title,
                    "candidate_url": url,
                    "title_url_match": True,
                },
                {
                    "kind": "official_detail",
                    "reason_code": "canonical_url_match",
                    "supports_publish": True,
                    "candidate_title": title,
                    "candidate_url": url,
                    "title_url_match": True,
                },
            ],
        )
        report = analyze_flip_rate(
            result_rows=_repeat(result),
            post_ids=["11694035"],
            repeats=5,
            blind_judge={
                "11694035": {
                    "acceptable_outcomes": [
                        {
                            "public_title": title,
                            "public_url": url,
                            "candidate_title": None,
                            "candidate_url": None,
                            "decision_status": "publish",
                            "publish_allowed": True,
                            "candidate_preserved": False,
                            "bypassed_gate": False,
                            "scope_kind": "current_work",
                            "required_direct_bridge_sources": [
                                "explicit_alias_relation",
                                "official_detail_url",
                            ],
                            "required_evidence_kinds": ["alias_relation", "official_detail"],
                            "required_evidence_reason_codes": [
                                "verified_explicit_alias",
                                "canonical_url_match",
                            ],
                            "required_publish_supporting_evidence_kinds": [
                                "alias_relation",
                                "official_detail",
                            ],
                            "required_publish_supporting_evidence_reason_codes": [
                                "verified_explicit_alias",
                                "canonical_url_match",
                            ],
                            "required_reason_codes": ["serialized_public_identity_published"],
                            "forbidden_reason_codes": ["serialized_public_identity_scrubbed"],
                            "require_fingerprint": True,
                            "require_contract_version": "promotion_contract_v2",
                        }
                    ]
                }
            },
        )

        row = report["rows"][0]
        self.assertEqual(report["gate"], "GO")
        self.assertEqual(row["matched_acceptable_outcome_index"], 0)
        self.assertEqual(row["expected_mismatch_reasons"], [])
        self.assertEqual(row["stable_outcome"]["public_title"], title)
        self.assertEqual(row["stable_outcome"]["public_url"], url)
        self.assertEqual(
            row["stable_outcome"]["direct_bridge_sources"],
            ["explicit_alias_relation", "official_detail_url"],
        )
        self.assertEqual(
            row["stable_outcome"]["evidence_kinds"],
            ["alias_relation", "official_detail"],
        )
        self.assertEqual(
            row["stable_outcome"]["evidence_reason_codes"],
            ["verified_explicit_alias", "canonical_url_match"],
        )

    def test_title_match_without_required_provenance_fails_closed(self):
        result = _contract_result_row(
            11663514,
            public_title="마탄 속의 제국",
            public_url="https://novel.munpia.com/486006",
            publish_allowed=True,
            candidate_preserved=False,
            reason_codes=["serialized_public_identity_published"],
        )
        report = analyze_flip_rate(
            result_rows=_repeat(result),
            post_ids=["11663514"],
            repeats=5,
            blind_judge={
                "11663514": {
                    "acceptable_outcomes": [
                        _acceptable_outcome(
                            public_title="마탄 속의 제국",
                            public_url="https://novel.munpia.com/486006",
                            candidate_title=None,
                            candidate_url=None,
                            decision_status="publish",
                            publish_allowed=True,
                            candidate_preserved=False,
                            scope_kind="current_work",
                            required_reason_codes=["serialized_public_identity_published"],
                            required_direct_bridge_sources=["source_native_url"],
                            required_evidence_kinds=["source_url", "image_ocr"],
                            required_evidence_reason_codes=[
                                "source_native_url_match",
                                "ocr_catalog_official_title",
                            ],
                        )
                    ]
                }
            },
        )

        reasons = report["rows"][0]["mismatch_reasons"]
        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn(
            'acceptable_outcomes[0].required_direct_bridge_sources_missing=["source_native_url"]',
            reasons,
        )
        self.assertIn(
            'acceptable_outcomes[0].required_evidence_kinds_missing=["source_url","image_ocr"]',
            reasons,
        )
        self.assertIn(
            'acceptable_outcomes[0].required_evidence_reason_codes_missing=["source_native_url_match","ocr_catalog_official_title"]',
            reasons,
        )

    def test_safe_hold_contract_separates_candidate_from_public_identity(self):
        title = "그레이스 길들이기"
        url = "https://ridibooks.com/books/1434007593"
        result = _contract_result_row(
            11682761,
            candidate_title=title,
            candidate_url=url,
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            reason_codes=["scope_context_only", "serialized_public_identity_scrubbed"],
            scope_kind="context_only",
        )
        outcome = row_outcome(result)

        self.assertIsNone(outcome["public_title"])
        self.assertIsNone(outcome["public_url"])
        self.assertEqual(outcome["candidate_title"], title)
        self.assertEqual(outcome["candidate_url"], url)
        self.assertEqual(outcome["title"], title)  # legacy compatibility only

        report = analyze_flip_rate(
            result_rows=_repeat(result),
            post_ids=["11682761"],
            repeats=5,
            blind_judge={
                "11682761": {
                    "acceptable_outcomes": [
                        _acceptable_outcome(
                            public_title=None,
                            public_url=None,
                            candidate_title=title,
                            candidate_url=url,
                            decision_status="candidate_only",
                            publish_allowed=False,
                            candidate_preserved=True,
                            scope_kind="context_only",
                            required_reason_codes=["serialized_public_identity_scrubbed"],
                        )
                    ]
                }
            },
        )

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["rows"][0]["matched_acceptable_outcome_index"], 0)

    def test_safe_hold_contract_rejects_stale_public_identity_leak(self):
        result = _contract_result_row(
            11682761,
            public_title="새면의 성녀",
            public_url="https://novelpia.com/novel/1",
            candidate_title="새면의 성녀",
            candidate_url="https://novelpia.com/novel/1",
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            reason_codes=["serialized_public_identity_scrubbed"],
            scope_kind="context_only",
        )
        report = analyze_flip_rate(
            result_rows=_repeat(result),
            post_ids=["11682761"],
            repeats=5,
            blind_judge={
                "11682761": {
                    "acceptable_outcomes": [
                        _acceptable_outcome(
                            public_title=None,
                            public_url=None,
                            candidate_title="새면의 성녀",
                            candidate_url="https://novelpia.com/novel/1",
                            decision_status="candidate_only",
                            publish_allowed=False,
                            candidate_preserved=True,
                            scope_kind="context_only",
                            required_reason_codes=["serialized_public_identity_scrubbed"],
                        )
                    ]
                }
            },
        )

        row = report["rows"][0]
        self.assertEqual(report["gate"], "NO-GO")
        self.assertFalse(row["blind_judge_expected_match"])
        self.assertEqual(row["mismatch_reasons"], row["expected_mismatch_reasons"])
        self.assertTrue(any(".public_title:" in reason for reason in row["expected_mismatch_reasons"]))
        self.assertTrue(any(".public_url:" in reason for reason in row["expected_mismatch_reasons"]))

    def test_contract_rejects_bypassed_gate_true(self):
        result = _contract_result_row(
            1,
            candidate_title="후보",
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            bypassed_gate=True,
            reason_codes=["scope_context_only"],
            scope_kind="context_only",
        )
        report = analyze_flip_rate(
            result_rows=_repeat(result),
            post_ids=["1"],
            repeats=5,
            blind_judge={
                "1": {
                    "acceptable_outcomes": [
                        _acceptable_outcome(
                            public_title=None,
                            public_url=None,
                            candidate_title="후보",
                            candidate_url=None,
                            decision_status="candidate_only",
                            publish_allowed=False,
                            candidate_preserved=True,
                            bypassed_gate=False,
                            scope_kind="context_only",
                            required_reason_codes=["scope_context_only"],
                        )
                    ]
                }
            },
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertTrue(
            any(".bypassed_gate:" in reason for reason in report["rows"][0]["expected_mismatch_reasons"])
        )

    def test_contract_requires_fingerprint_and_version_fail_closed(self):
        result = _contract_result_row(
            1,
            candidate_title="후보",
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            reason_codes=["scope_context_only"],
            scope_kind="context_only",
            contract_version=None,
            input_fingerprint=None,
        )
        report = analyze_flip_rate(
            result_rows=_repeat(result),
            post_ids=["1"],
            repeats=5,
            blind_judge={
                "1": {
                    "acceptable_outcomes": [
                        _acceptable_outcome(
                            public_title=None,
                            public_url=None,
                            candidate_title="후보",
                            candidate_url=None,
                            decision_status="candidate_only",
                            publish_allowed=False,
                            candidate_preserved=True,
                            scope_kind="context_only",
                            required_reason_codes=["scope_context_only"],
                        )
                    ]
                }
            },
        )

        reasons = report["rows"][0]["expected_mismatch_reasons"]
        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn(
            "acceptable_outcomes[0].input_fingerprint:required_lowercase_sha256_missing_or_invalid",
            reasons,
        )
        self.assertIn(
            'acceptable_outcomes[0].contract_version:expected="promotion_contract_v2":actual=null',
            reasons,
        )

    def test_require_fingerprint_true_accepts_only_lowercase_sha256(self):
        expected = _acceptable_outcome(
            public_title=None,
            public_url=None,
            candidate_title="후보",
            candidate_url=None,
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            scope_kind="context_only",
            required_reason_codes=["scope_context_only"],
            require_fingerprint=True,
        )
        for fingerprint, expected_gate in (
            (_CANONICAL_CONTRACT_VALUE, "GO"),
            ("F" * 64, "NO-GO"),
            ("x", "NO-GO"),
        ):
            with self.subTest(fingerprint=fingerprint):
                result = _contract_result_row(
                    1,
                    candidate_title="후보",
                    decision_status="candidate_only",
                    publish_allowed=False,
                    candidate_preserved=True,
                    reason_codes=["scope_context_only"],
                    scope_kind="context_only",
                    input_fingerprint=fingerprint,
                )
                report = analyze_flip_rate(
                    result_rows=_repeat(result),
                    post_ids=["1"],
                    repeats=5,
                    blind_judge={"1": {"acceptable_outcomes": [expected]}},
                )
                self.assertEqual(report["gate"], expected_gate)
                if expected_gate != "GO":
                    self.assertTrue(
                        any(
                            "required_lowercase_sha256_missing_or_invalid" in reason
                            for reason in report["rows"][0]["mismatch_reasons"]
                        )
                    )

    def test_v2_missing_surface_is_reported_and_blocks_go(self):
        result = _contract_result_row(
            1,
            candidate_title="후보",
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            reason_codes=["scope_context_only"],
            scope_kind="context_only",
        )
        identity = result["analysis_result"]["identity"]
        del identity["publish_contract_trace"]
        del identity["candidate_ledger"]["publish_contract_trace"]
        expected = _acceptable_outcome(
            public_title=None,
            public_url=None,
            candidate_title="후보",
            candidate_url=None,
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            scope_kind="context_only",
            required_reason_codes=["scope_context_only"],
        )

        report = analyze_flip_rate(
            result_rows=_repeat(result),
            post_ids=["1"],
            repeats=5,
            blind_judge={"1": {"acceptable_outcomes": [expected]}},
        )

        issues = report["rows"][0]["stable_outcome"]["contract_consistency_issues"]
        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("identity_publish_contract_trace_missing", issues)
        self.assertIn("ledger_publish_contract_trace_missing", issues)

    def test_v2_cross_surface_mismatch_is_reported_and_blocks_go(self):
        result = _contract_result_row(
            1,
            candidate_title="후보",
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            reason_codes=["scope_context_only"],
            scope_kind="context_only",
        )
        result["analysis_result"]["identity"]["candidate_ledger"]["promotion_decision"][
            "reason_codes"
        ] = ["forged_reason"]
        expected = _acceptable_outcome(
            public_title=None,
            public_url=None,
            candidate_title="후보",
            candidate_url=None,
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            scope_kind="context_only",
            required_reason_codes=["scope_context_only"],
        )

        report = analyze_flip_rate(
            result_rows=_repeat(result),
            post_ids=["1"],
            repeats=5,
            blind_judge={"1": {"acceptable_outcomes": [expected]}},
        )

        issues = report["rows"][0]["stable_outcome"]["contract_consistency_issues"]
        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("promotion_decision_reason_codes_surface_mismatch", issues)

    def test_negative_or_wrong_candidate_evidence_cannot_satisfy_publish_provenance(self):
        title = "마탄 속의 제국"
        url = "https://novel.munpia.com/486006"
        result = _contract_result_row(
            1,
            public_title=title,
            public_url=url,
            publish_allowed=True,
            candidate_preserved=False,
            reason_codes=["serialized_public_identity_published"],
            direct_bridge_sources=["source_native_url"],
            promotion_evidence=[
                {
                    "kind": "source_url",
                    "reason_code": "source_native_url_match",
                    "supports_publish": False,
                    "candidate_title": title,
                    "candidate_url": url,
                    "title_url_match": True,
                },
                {
                    "kind": "image_ocr",
                    "reason_code": "ocr_catalog_official_title",
                    "supports_publish": True,
                    "candidate_title": "다른 작품",
                    "candidate_url": url,
                    "title_url_match": True,
                },
            ],
        )
        expected = _acceptable_outcome(
            public_title=title,
            public_url=url,
            candidate_title=None,
            candidate_url=None,
            decision_status="publish",
            publish_allowed=True,
            candidate_preserved=False,
            scope_kind="current_work",
            required_reason_codes=["serialized_public_identity_published"],
            required_direct_bridge_sources=["source_native_url"],
            required_evidence_kinds=["source_url", "image_ocr"],
            required_evidence_reason_codes=[
                "source_native_url_match",
                "ocr_catalog_official_title",
            ],
        )

        report = analyze_flip_rate(
            result_rows=_repeat(result),
            post_ids=["1"],
            repeats=5,
            blind_judge={"1": {"acceptable_outcomes": [expected]}},
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertTrue(
            any(
                "required_publish_supporting_evidence_kinds_missing" in reason
                for reason in report["rows"][0]["mismatch_reasons"]
            )
        )

    def test_legacy_contract_cannot_authorize_blocked_candidate_as_public(self):
        result = _contract_result_row(
            1,
            candidate_title="차단 후보",
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            reason_codes=["scope_context_only"],
            scope_kind="context_only",
        )
        report = analyze_flip_rate(
            result_rows=_repeat(result),
            post_ids=["1"],
            repeats=5,
            blind_judge={
                "1": {
                    "expected_status": "promotion_blocked",
                    "expected_title": "차단 후보",
                }
            },
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn(
            "legacy_expected_contract_nonpublic_status_not_authoritative",
            report["rows"][0]["mismatch_reasons"],
        )

    def test_duplicate_repeat_binding_cannot_satisfy_five_independent_repeats(self):
        result = _contract_result_row(
            1,
            candidate_title="후보",
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            reason_codes=["scope_context_only"],
            scope_kind="context_only",
        )
        rows = _repeat(result)
        for row in rows:
            row["run_meta"]["run_id"] = "same-run"
        expected = _acceptable_outcome(
            public_title=None,
            public_url=None,
            candidate_title="후보",
            candidate_url=None,
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            scope_kind="context_only",
            required_reason_codes=["scope_context_only"],
        )

        report = analyze_flip_rate(
            result_rows=rows,
            post_ids=["1"],
            repeats=5,
            blind_judge={"1": {"acceptable_outcomes": [expected]}},
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertFalse(report["rows"][0]["independent_repeats_present"])

    def test_mixed_runtime_signature_cannot_satisfy_homogeneous_gate(self):
        result = _contract_result_row(
            1,
            candidate_title="후보",
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            reason_codes=["scope_context_only"],
            scope_kind="context_only",
        )
        rows = _repeat(result)
        rows[-1]["run_meta"]["model"] = "different-model"
        expected = _acceptable_outcome(
            public_title=None,
            public_url=None,
            candidate_title="후보",
            candidate_url=None,
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            scope_kind="context_only",
            required_reason_codes=["scope_context_only"],
        )

        report = analyze_flip_rate(
            result_rows=rows,
            post_ids=["1"],
            repeats=5,
            blind_judge={"1": {"acceptable_outcomes": [expected]}},
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertFalse(report["rows"][0]["runtime_signatures_valid"])

    def test_runtime_fingerprint_surfaces_are_raw_typed_and_exact(self):
        result = _contract_result_row(
            1,
            candidate_title="후보",
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            reason_codes=["scope_context_only"],
            scope_kind="context_only",
        )
        expected = _acceptable_outcome(
            public_title=None,
            public_url=None,
            candidate_title="후보",
            candidate_url=None,
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            scope_kind="context_only",
            required_reason_codes=["scope_context_only"],
        )
        mutations = (
            ("whitespace", " " + "a" * 64 + " "),
            ("non_string", 123),
            ("conflict", "b" * 64),
        )
        for label, alias_value in mutations:
            with self.subTest(label=label):
                rows = _repeat(result)
                for row in rows:
                    row["run_meta"]["stable_runtime_fingerprint_sha256"] = alias_value
                report = analyze_flip_rate(
                    result_rows=rows,
                    post_ids=["1"],
                    repeats=5,
                    blind_judge={"1": {"acceptable_outcomes": [expected]}},
                )
                self.assertEqual(report["gate"], "NO-GO")
                self.assertFalse(report["rows"][0]["runtime_signatures_valid"])

    def test_analyze_rejects_duplicate_requested_post_ids(self):
        result = _contract_result_row(
            1,
            candidate_title="후보",
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            reason_codes=["scope_context_only"],
            scope_kind="context_only",
        )
        expected = _acceptable_outcome(
            public_title=None,
            public_url=None,
            candidate_title="후보",
            candidate_url=None,
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            scope_kind="context_only",
            required_reason_codes=["scope_context_only"],
        )
        report = analyze_flip_rate(
            result_rows=_repeat(result),
            post_ids=["1", "1"],
            repeats=5,
            blind_judge={"1": {"acceptable_outcomes": [expected]}},
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertFalse(report["summary"]["post_ids_unique"])

    def test_acceptable_outcomes_or_contract_reports_matched_index(self):
        result = _contract_result_row(
            1,
            candidate_title="후보",
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            reason_codes=["scope_context_only"],
            scope_kind="context_only",
        )
        report = analyze_flip_rate(
            result_rows=_repeat(result),
            post_ids=["1"],
            repeats=5,
            blind_judge={
                "1": {
                    "acceptable_outcomes": [
                        _acceptable_outcome(
                            public_title="다른 작품",
                            public_url="https://example.invalid/other",
                            candidate_title=None,
                            candidate_url=None,
                            decision_status="publish",
                            publish_allowed=True,
                            candidate_preserved=False,
                            scope_kind="current_work",
                            required_reason_codes=["scope_current_work"],
                            required_direct_bridge_sources=["source_native_url"],
                            required_evidence_kinds=["official_detail"],
                            required_evidence_reason_codes=["canonical_url_match"],
                        ),
                        _acceptable_outcome(
                            public_title=None,
                            public_url=None,
                            candidate_title="후보",
                            candidate_url=None,
                            decision_status="candidate_only",
                            publish_allowed=False,
                            candidate_preserved=True,
                            scope_kind="context_only",
                            required_reason_codes=["scope_context_only"],
                        ),
                    ]
                }
            },
        )

        row = report["rows"][0]
        self.assertEqual(report["gate"], "GO")
        self.assertEqual(row["matched_acceptable_outcome_index"], 1)
        self.assertEqual(row["expected_mismatch_reasons"], [])
        self.assertTrue(row["acceptable_outcome_mismatch_reasons"][0]["reasons"])

    def test_empty_or_malformed_acceptable_outcome_fails_closed(self):
        result = _contract_result_row(1, public_title="작품", publish_allowed=True)
        for acceptable_outcomes in ([], [{}], "not-a-list"):
            with self.subTest(acceptable_outcomes=acceptable_outcomes):
                report = analyze_flip_rate(
                    result_rows=_repeat(result),
                    post_ids=["1"],
                    repeats=5,
                    blind_judge={"1": {"acceptable_outcomes": acceptable_outcomes}},
                )
                self.assertEqual(report["gate"], "NO-GO")
                self.assertFalse(report["rows"][0]["blind_judge_expected_match"])
                self.assertTrue(report["rows"][0]["expected_mismatch_reasons"])

    def test_required_candidate_inventory_pair_is_authoritative_subset_constraint(self):
        pair = {"title": "정답 후보", "url": "https://novelpia.com/novel/77"}
        result = _contract_result_row(
            1,
            candidate_title=pair["title"],
            candidate_url=pair["url"],
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            scope_kind="context_only",
            candidate_inventory_sources=[
                {"official_title": pair["title"], "heretic_url": pair["url"]},
                {"official_title": "보조 후보", "heretic_url": None},
            ],
        )
        expected = _acceptable_outcome(
            public_title=None,
            public_url=None,
            candidate_title=pair["title"],
            candidate_url=pair["url"],
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            scope_kind="context_only",
            required_reason_codes=["scope_context_only", "scope_not_current_work"],
            required_candidate_inventory_pairs=[pair],
        )

        report = analyze_flip_rate(
            result_rows=_repeat(result),
            post_ids=["1"],
            repeats=5,
            blind_judge={"1": {"acceptable_outcomes": [expected]}},
        )

        self.assertEqual(report["gate"], "GO", report["rows"][0]["mismatch_reasons"])
        self.assertTrue(report["rows"][0]["expected_contract_authoritative"])
        self.assertEqual(report["rows"][0]["matched_acceptable_outcome_index"], 0)

        selected_without_inventory = _contract_result_row(
            1,
            candidate_title=pair["title"],
            candidate_url=pair["url"],
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            scope_kind="context_only",
        )
        rejected = analyze_flip_rate(
            result_rows=_repeat(selected_without_inventory),
            post_ids=["1"],
            repeats=5,
            blind_judge={"1": {"acceptable_outcomes": [expected]}},
        )
        self.assertEqual(rejected["gate"], "NO-GO")
        self.assertTrue(
            any(
                "required_candidate_inventory_pairs_missing" in reason
                for reason in rejected["rows"][0]["mismatch_reasons"]
            )
        )

    def test_required_candidate_inventory_pairs_reject_malformed_empty_duplicate_and_unknown(self):
        base = _acceptable_outcome(
            public_title=None,
            public_url=None,
            candidate_title="정답 후보",
            candidate_url=None,
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            scope_kind="context_only",
            required_reason_codes=["scope_context_only", "scope_not_current_work"],
            required_candidate_inventory_pairs=[{"title": "정답 후보", "url": None}],
        )
        result = _contract_result_row(
            1,
            candidate_title="정답 후보",
            decision_status="candidate_only",
            publish_allowed=False,
            candidate_preserved=True,
            scope_kind="context_only",
            candidate_inventory_sources=[{"official_title": "정답 후보"}],
        )
        mutations = {
            "empty": [],
            "duplicate": [
                {"title": "정답 후보", "url": None},
                {"title": "정답 후보", "url": None},
            ],
            "unknown_pair_field": [{"title": "정답 후보", "url": None, "extra": True}],
            "malformed_pair": [{"title": "", "url": None}],
        }
        for name, pairs in mutations.items():
            with self.subTest(name=name):
                expected = copy.deepcopy(base)
                expected["required_candidate_inventory_pairs"] = pairs
                report = analyze_flip_rate(
                    result_rows=_repeat(result),
                    post_ids=["1"],
                    repeats=5,
                    blind_judge={"1": {"acceptable_outcomes": [expected]}},
                )
                self.assertEqual(report["gate"], "NO-GO")
                self.assertFalse(report["rows"][0]["expected_contract_authoritative"])
                self.assertTrue(report["rows"][0]["mismatch_reasons"])

    def test_runtime_plan_audit_accepts_exact_25_complete_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path, results, _manifests, _judge = _write_runtime_plan_fixture(Path(tmp))

            audit = audit_run_plan_runtime_contract(
                run_plan_path=plan_path,
                result_paths=results,
                post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                repeats=5,
            )

        self.assertEqual(audit["gate"], "GO", audit["issues"])
        self.assertEqual(audit["summary"]["planned_run_count"], 25)
        self.assertEqual(audit["summary"]["provided_result_count"], 25)
        self.assertEqual(audit["summary"]["manifest_count"], 25)
        self.assertEqual(audit["summary"]["unique_run_id_count"], 25)
        self.assertEqual(audit["summary"]["row_derived_config_hash_unique_count"], 1)
        self.assertEqual(audit["summary"]["row_derived_config_hash"], "test-config-v1")
        self.assertEqual(audit["summary"]["execution_adopted_completion_count"], 25)
        self.assertEqual(audit["summary"]["execution_child_started_count"], 25)
        self.assertEqual(audit["summary"]["execution_failed_attempt_count"], 0)
        self.assertEqual(audit["summary"]["execution_indeterminate_attempt_count"], 0)
        self.assertTrue(all(run["gate"] == "GO" for run in audit["runs"]))

    def test_runtime_plan_audit_explicitly_rejects_checkpoint_path_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path, results, _manifests, _judge = _write_runtime_plan_fixture(
                Path(tmp)
            )
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["planned_runs"][1]["checkpoint_jsonl"] = plan["planned_runs"][0][
                "checkpoint_jsonl"
            ]
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            audit = audit_run_plan_runtime_contract(
                run_plan_path=plan_path,
                result_paths=results,
                post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                repeats=5,
            )
        self.assertEqual(audit["gate"], "NO-GO")
        self.assertIn("run_plan_checkpoint_paths_duplicate", audit["issues"])
        self.assertIn("run_plan_runtime_artifact_paths_overlap", audit["issues"])

    def test_runtime_plan_audit_rejects_adoption_or_child_started_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, results, _manifests, _judge = _write_runtime_plan_fixture(root)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            adoption_path = Path(
                plan["planned_runs"][0]["adopted_completion_receipt_json"]
            )
            adoption = json.loads(adoption_path.read_text(encoding="utf-8"))
            adoption["artifact_binding"]["output_sha256"] = "0" * 64
            adoption_path.write_text(json.dumps(adoption), encoding="utf-8")
            audit = audit_run_plan_runtime_contract(
                run_plan_path=plan_path,
                result_paths=results,
                post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                repeats=5,
            )
            self.assertEqual(audit["gate"], "NO-GO")
            self.assertIn("execution_adoption_contract_not_go", audit["issues"])

            plan_path, results, _manifests, _judge = _write_runtime_plan_fixture(
                root / "child-mutation"
            )
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            child_path = Path(plan["planned_runs"][0]["attempt_dir"]) / (
                "attempt_001.child_started.json"
            )
            child = json.loads(child_path.read_text(encoding="utf-8"))
            child["process_creation_token"] = "mutated"
            child_path.write_text(json.dumps(child), encoding="utf-8")
            audit = audit_run_plan_runtime_contract(
                run_plan_path=plan_path,
                result_paths=results,
                post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                repeats=5,
            )
            self.assertEqual(audit["gate"], "NO-GO")
            self.assertIn("execution_adoption_contract_not_go", audit["issues"])

    def test_runtime_plan_audit_rejects_plan_or_bound_judge_mutation_after_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, results, _manifests, _judge = _write_runtime_plan_fixture(
                root / "plan-mutation"
            )
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["generated_at"] = "mutated-after-results"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            audit = audit_run_plan_runtime_contract(
                run_plan_path=plan_path,
                result_paths=results,
                post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                repeats=5,
            )
            self.assertEqual(audit["gate"], "NO-GO")
            self.assertIn("run_plan_self_binding_mismatch", audit["issues"])

            plan_path, results, _manifests, judge_path = _write_runtime_plan_fixture(
                root / "judge-mutation"
            )
            judge = json.loads(judge_path.read_text(encoding="utf-8"))
            judge["rows"][0]["acceptable_outcomes"][0]["public_title"] = (
                "수동 삽입된 잘못된 작품"
            )
            judge_path.write_text(
                json.dumps(judge, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            audit = audit_run_plan_runtime_contract(
                run_plan_path=plan_path,
                result_paths=results,
                post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                repeats=5,
            )
            self.assertEqual(audit["gate"], "NO-GO")
            self.assertTrue(
                any(
                    issue.startswith("blind_judge_binding_invalid:ValueError:")
                    and "deterministic builder derivation" in issue
                    for issue in audit["issues"]
                ),
                audit["issues"],
            )

    def test_runtime_plan_audit_accepts_only_clean_or_fully_recovered_row_search_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, results, _manifests, _judge = _write_runtime_plan_fixture(
                root,
                first_search_health={
                    "status": "SEARCH_DEGRADED_RECOVERED",
                    "degraded": 1,
                    "degraded_recovered": 1,
                    "unrecovered_degraded": 0,
                },
            )

            audit = audit_run_plan_runtime_contract(
                run_plan_path=plan_path,
                result_paths=results,
                post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                repeats=5,
            )

        self.assertEqual(audit["gate"], "GO", audit["issues"])
        self.assertEqual(
            audit["summary"]["row_search_health_status_counts"],
            {"SEARCH_DEGRADED_RECOVERED": 1, "ok": 24},
        )

    def test_runtime_plan_audit_rejects_row_search_health_missing_degraded_or_unrecovered(self):
        mutations = {
            "missing": None,
            "degraded": {
                "status": "SEARCH_DEGRADED",
                "degraded": 1,
                "degraded_recovered": 0,
                "unrecovered_degraded": 1,
            },
            "missing_status": {
                "degraded": 0,
                "degraded_recovered": 0,
                "unrecovered_degraded": 0,
            },
            "unrecovered": {
                "status": "SEARCH_DEGRADED_RECOVERED",
                "degraded": 2,
                "degraded_recovered": 1,
                "unrecovered_degraded": 1,
            },
        }
        for name, health in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                plan_path, results, _manifests, _judge = _write_runtime_plan_fixture(root)
                payload = json.loads(results[0].read_text(encoding="utf-8"))
                if health is None:
                    payload[0]["run_meta"].pop("search_health")
                else:
                    payload[0]["run_meta"]["search_health"] = health
                results[0].write_text(json.dumps(payload), encoding="utf-8")

                audit = audit_run_plan_runtime_contract(
                    run_plan_path=plan_path,
                    result_paths=results,
                    post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                    repeats=5,
                )

                self.assertEqual(audit["gate"], "NO-GO")
                self.assertTrue(
                    any("row_run_meta_search_health" in issue for issue in audit["runs"][0]["issues"])
                )

    def test_runtime_plan_audit_rejects_deleted_multiline_or_sha_mutated_input(self):
        mutations = ("deleted", "two_rows", "content_mutated", "plan_sha_mutated")
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                plan_path, results, _manifests, _judge = _write_runtime_plan_fixture(root)
                plan = json.loads(plan_path.read_text(encoding="utf-8"))
                run = plan["planned_runs"][0]
                input_path = Path(run["input_jsonl"])
                original_row = json.loads(input_path.read_text(encoding="utf-8"))
                if mutation == "deleted":
                    input_path.unlink()
                elif mutation == "two_rows":
                    write_probe_input([original_row, original_row], input_path)
                elif mutation == "content_mutated":
                    write_probe_input([{**original_row, "title": "mutated"}], input_path)
                else:
                    run["input_sha256"] = "c" * 64
                    plan_path.write_text(json.dumps(plan), encoding="utf-8")

                audit = audit_run_plan_runtime_contract(
                    run_plan_path=plan_path,
                    result_paths=results,
                    post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                    repeats=5,
                )

                self.assertEqual(audit["gate"], "NO-GO")
                run_issues = audit["runs"][0]["issues"]
                if mutation == "deleted":
                    self.assertIn("input_not_found", run_issues)
                elif mutation == "two_rows":
                    self.assertIn("input_row_count_not_one", run_issues)
                    self.assertIn("input_file_sha256_mismatch", run_issues)
                else:
                    self.assertIn("input_file_sha256_mismatch", run_issues)
                    self.assertIn("input_canonical_sha256_mismatch", run_issues)

    def test_runtime_plan_audit_rejects_search_endpoint_count_contradictions(self):
        fields = (
            "mcp_health_checked_endpoint_count",
            "mcp_requested_endpoint_count_before_health_filter",
            "mcp_healthy_endpoint_count",
            "mcp_endpoint_count_after_health_filter",
        )
        for field in fields:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                plan_path, results, manifests, _judge = _write_runtime_plan_fixture(root)
                manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
                manifest[field] = 0
                manifests[0].write_text(json.dumps(manifest), encoding="utf-8")

                audit = audit_run_plan_runtime_contract(
                    run_plan_path=plan_path,
                    result_paths=results,
                    post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                    repeats=5,
                )

                self.assertEqual(audit["gate"], "NO-GO")
                self.assertIn(f"manifest_{field}_mismatch", audit["runs"][0]["issues"])

    def test_runtime_plan_audit_rejects_vlm_ready_contradictions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, results, manifests, _judge = _write_runtime_plan_fixture(root)
            manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
            manifest.update(
                {
                    "vlm_ocr_semantic_review_blocker": True,
                    "vlm_ocr_semantic_review_skip_reasons": ["vlm_disabled"],
                    "vlm_ocr_semantic_review_skip_reason": "vlm_disabled",
                    "vlm_ocr_semantic_review_blocker_code": "image_posts_without_vlm_ocr_ready",
                    "vlm_ocr_semantic_review_blocker_action": "rerun_with_vlm_on_ocr_on",
                }
            )
            manifests[0].write_text(json.dumps(manifest), encoding="utf-8")

            audit = audit_run_plan_runtime_contract(
                run_plan_path=plan_path,
                result_paths=results,
                post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                repeats=5,
            )

        self.assertEqual(audit["gate"], "NO-GO")
        run_issues = audit["runs"][0]["issues"]
        self.assertIn("manifest_vlm_ocr_semantic_review_blocker_mismatch", run_issues)
        self.assertIn("manifest_vlm_ocr_semantic_review_skip_reasons_mismatch", run_issues)
        self.assertIn("manifest_vlm_ocr_semantic_review_blocker_code_mismatch", run_issues)
        self.assertIn("manifest_vlm_ocr_semantic_review_blocker_action_mismatch", run_issues)

    def test_runtime_plan_audit_rejects_mapping_command_manifest_and_row_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, results, manifests, _judge = _write_runtime_plan_fixture(root)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))

            bad_plan = copy.deepcopy(plan)
            bad_plan["planned_runs"][0]["command_argv"].extend(["--parallel", "1"])
            plan_path.write_text(json.dumps(bad_plan), encoding="utf-8")
            audit = audit_run_plan_runtime_contract(
                run_plan_path=plan_path,
                result_paths=results[:-1],
                post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                repeats=5,
            )
            self.assertEqual(audit["gate"], "NO-GO")
            self.assertIn("provided_results_do_not_exactly_match_run_plan", audit["issues"])
            self.assertTrue(any("command_parallel_mismatch" in issue for issue in audit["issues"]))

            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
            manifest["failed_count"] = 1
            manifest["dashboard_mode"] = "embedded"
            manifests[0].write_text(json.dumps(manifest), encoding="utf-8")
            result_payload = json.loads(results[0].read_text(encoding="utf-8"))
            result_payload[0]["run_meta"]["runtime_release_fingerprint_sha256"] = "c" * 64
            results[0].write_text(json.dumps(result_payload), encoding="utf-8")
            audit = audit_run_plan_runtime_contract(
                run_plan_path=plan_path,
                result_paths=results,
                post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                repeats=5,
            )
            self.assertEqual(audit["gate"], "NO-GO")
            self.assertTrue(any("manifest_failed_count_mismatch" in issue for issue in audit["issues"]))
            self.assertTrue(
                any("manifest_dashboard_mode_not_standalone_forward" in issue for issue in audit["issues"])
            )
            self.assertTrue(
                any(
                    "row_run_meta_runtime_release_fingerprint_sha256_runtime_contract_mismatch" in issue
                    for issue in audit["issues"]
                )
            )

    def test_runtime_plan_audit_requires_exact_n5_x5(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_path, results, _manifests, _judge = _write_runtime_plan_fixture(Path(tmp))
            audit = audit_run_plan_runtime_contract(
                run_plan_path=plan_path,
                result_paths=results,
                post_ids=list(_RUNTIME_AUDIT_POST_IDS[:4]),
                repeats=5,
            )

        self.assertEqual(audit["gate"], "NO-GO")
        self.assertIn("runtime_contract_requires_exact_five_post_ids", audit["issues"])
        self.assertIn("runtime_contract_requires_exact_25_runs", audit["issues"])

    def test_runtime_plan_audit_rejects_command_path_and_required_env_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, results, _manifests, _judge = _write_runtime_plan_fixture(
                root / "command"
            )
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            argv = plan["planned_runs"][0]["command_argv"]
            argv[argv.index("--input") + 1] = str(root / "wrong-input.jsonl")
            argv[argv.index("--output") + 1] = str(root / "wrong-output.json")
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            audit = audit_run_plan_runtime_contract(
                run_plan_path=plan_path,
                result_paths=results,
                post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                repeats=5,
            )
            self.assertEqual(audit["gate"], "NO-GO")
            self.assertTrue(
                any("command_input_not_bound_to_planned_input_jsonl" in issue for issue in audit["issues"])
            )
            self.assertTrue(
                any("command_output_not_bound_to_planned_output_json" in issue for issue in audit["issues"])
            )

            plan_path, results, _manifests, _judge = _write_runtime_plan_fixture(
                root / "required-env"
            )
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["planned_runs"][0]["required_env"]["TEST_REQUIRED_ENV"] = "drift"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            audit = audit_run_plan_runtime_contract(
                run_plan_path=plan_path,
                result_paths=results,
                post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                repeats=5,
            )
            self.assertEqual(audit["gate"], "NO-GO")
            self.assertTrue(
                any("required_env_not_exactly_bound_to_plan" in issue for issue in audit["issues"])
            )

    def test_runtime_plan_audit_rejects_fingerprint_alias_and_row_config_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, results, manifests, _judge = _write_runtime_plan_fixture(
                root / "fingerprint"
            )
            manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
            manifest["stable_runtime_fingerprint_sha256"] = "B" * 64
            manifest["runtime_fingerprint_sha256"] = "c" * 64
            manifests[0].write_text(json.dumps(manifest), encoding="utf-8")
            audit = audit_run_plan_runtime_contract(
                run_plan_path=plan_path,
                result_paths=results,
                post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                repeats=5,
            )
            self.assertEqual(audit["gate"], "NO-GO")
            self.assertTrue(
                any("manifest_stable_runtime_fingerprint_sha256_invalid" in issue for issue in audit["issues"])
            )
            self.assertTrue(
                any("manifest_fingerprint_aliases_mismatch" in issue for issue in audit["issues"])
            )

            plan_path, results, _manifests, _judge = _write_runtime_plan_fixture(
                root / "config"
            )
            payload = json.loads(results[0].read_text(encoding="utf-8"))
            payload[0]["run_meta"]["config_hash"] = "different-derived-config"
            results[0].write_text(json.dumps(payload), encoding="utf-8")
            audit = audit_run_plan_runtime_contract(
                run_plan_path=plan_path,
                result_paths=results,
                post_ids=list(_RUNTIME_AUDIT_POST_IDS),
                repeats=5,
            )
            self.assertEqual(audit["gate"], "NO-GO")
            self.assertIn(
                "row_derived_config_hash_not_uniform_nonempty_across_25", audit["issues"]
            )

    def test_build_run_plan_cli_emits_audit_compatible_runtime_and_env_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.jsonl"
            write_probe_input(
                [_input_row(post_id) for post_id in _RUNTIME_AUDIT_POST_IDS], source
            )
            plan_path = root / "plan.json"
            blind_judge_path = _write_bound_blind_judge(
                root, list(_RUNTIME_AUDIT_POST_IDS)
            )
            analysis_output_json = root / "analysis.json"
            analysis_output_md = root / "analysis.md"
            command = [
                sys.executable,
                "tools/safe_loss_flip_rate_probe.py",
                "build-run-plan",
                "--source-input",
                str(source),
                "--post-ids",
                ",".join(_RUNTIME_AUDIT_POST_IDS),
                "--repeats",
                "5",
                "--work-dir",
                str(root / "runs"),
                "--run-prefix",
                "cli-audit-compatible",
                "--manifest",
                str(plan_path),
                "--runtime-model",
                _RUNTIME_AUDIT_CONTRACT["model"],
                "--runtime-llm-mode",
                _RUNTIME_AUDIT_CONTRACT["llm_mode"],
                "--runtime-llm-endpoint",
                _RUNTIME_AUDIT_CONTRACT["llm_endpoint"],
                "--runtime-prompt-version",
                _RUNTIME_AUDIT_CONTRACT["prompt_version"],
                "--runtime-release-fingerprint-sha256",
                _RUNTIME_AUDIT_CONTRACT["runtime_release_fingerprint_sha256"],
                "--blind-judge",
                str(blind_judge_path),
                "--analysis-output-json",
                str(analysis_output_json),
                "--analysis-output-md",
                str(analysis_output_md),
                "--required-env",
                "TEST_REQUIRED_ENV=bound",
            ]
            completed = subprocess.run(
                command,
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(
                plan["runtime_contract"]["config_hash_policy"],
                "uniform_nonempty_row_derived",
            )
            self.assertEqual(plan["required_env"], plan["runtime_contract"]["required_env"])
            self.assertEqual(plan["required_env"]["TEST_REQUIRED_ENV"], "bound")
            self.assertEqual(
                plan["required_env"]["RUNTIME_RELEASE_FINGERPRINT_SHA256"],
                _RUNTIME_AUDIT_CONTRACT["runtime_release_fingerprint_sha256"],
            )
            self.assertEqual(len(plan["planned_runs"]), 25)
            self.assertEqual(
                plan["blind_judge_binding"]["byte_sha256"],
                _test_file_sha256(blind_judge_path),
            )
            self.assertRegex(
                plan["blind_judge_binding"]["source_bindings_canonical_sha256"],
                r"^[0-9a-f]{64}$",
            )
            self.assertRegex(
                plan["blind_judge_binding"]["source_binding_files_digest_sha256"],
                r"^[0-9a-f]{64}$",
            )
            self.assertEqual(plan["blind_judge_binding"]["scope"]["post_id_count"], 5)
            self.assertEqual(plan["blind_judge_binding"]["scope"]["repeats_required"], 5)
            self.assertEqual(
                plan["blind_judge_binding"]["scope"]["expected_independent_result_count"],
                25,
            )
            self.assertRegex(plan["plan_self_binding"]["canonical_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(
                plan["execution_claim_contract"]["version"],
                "independent-plan-execution-claim-v3",
            )
            self.assertFalse(
                plan["execution_claim_contract"][
                    "failed_child_rc_without_artifacts_may_retry"
                ]
            )
            analyze_argv = plan["analyze_command_argv"]
            for flag in ("--require-runtime-contract", "--fail-on-no-go"):
                self.assertEqual(analyze_argv.count(flag), 1)
            for option, expected in (
                ("--blind-judge", blind_judge_path),
                ("--run-plan", plan_path),
                ("--output-json", analysis_output_json),
                ("--output-md", analysis_output_md),
            ):
                self.assertEqual(analyze_argv.count(option), 1)
                self.assertEqual(Path(analyze_argv[analyze_argv.index(option) + 1]), expected)
            for run in plan["planned_runs"]:
                self.assertIn("attempt_dir", run)
                self.assertIn("adopted_completion_receipt_json", run)
                self.assertEqual(run["required_env"], plan["required_env"])
                argv = run["command_argv"]
                self.assertEqual(Path(argv[argv.index("--input") + 1]), Path(run["input_jsonl"]))
                self.assertEqual(Path(argv[argv.index("--output") + 1]), Path(run["output_json"]))
            plan_hash = _test_file_sha256(plan_path)
            input_hashes = {
                run["input_jsonl"]: _test_file_sha256(Path(run["input_jsonl"]))
                for run in plan["planned_runs"]
            }
            repeated = subprocess.run(
                command,
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual(_test_file_sha256(plan_path), plan_hash)
            self.assertEqual(
                {
                    path: _test_file_sha256(Path(path))
                    for path in input_hashes
                },
                input_hashes,
            )

    def test_built_analyze_command_is_executable_and_go(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, _results, _manifests, _judge_path = _write_runtime_plan_fixture(root)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))

            completed = subprocess.run(
                plan["analyze_command_argv"],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(Path(plan["analysis_output_json"]).read_text(encoding="utf-8"))
            self.assertEqual(report["gate"], "GO")
            self.assertEqual(report["runtime_contract_audit"]["gate"], "GO")

    def test_result_complete_then_blind_judge_mutation_is_runtime_no_go(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, _results, _manifests, judge_path = _write_runtime_plan_fixture(root)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            judge = json.loads(judge_path.read_text(encoding="utf-8"))
            judge["rows"][0]["acceptable_outcomes"][0]["public_title"] = "다른 작품"
            judge_path.write_text(json.dumps(judge, ensure_ascii=False), encoding="utf-8")

            completed = subprocess.run(
                plan["analyze_command_argv"],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )

            self.assertEqual(completed.returncode, 3, completed.stderr)
            report = json.loads(Path(plan["analysis_output_json"]).read_text(encoding="utf-8"))
            self.assertEqual(report["gate"], "NO-GO")
            self.assertEqual(report["runtime_contract_audit"]["gate"], "NO-GO")
            self.assertTrue(
                any(
                    issue.startswith("blind_judge_binding_invalid:ValueError:")
                    and "deterministic builder derivation" in issue
                    for issue in report["runtime_contract_audit"]["issues"]
                ),
                report["runtime_contract_audit"]["issues"],
            )

    def test_invalid_blind_judge_bytes_after_results_emit_no_go_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, _results, _manifests, judge_path = _write_runtime_plan_fixture(root)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            judge_path.write_text("{", encoding="utf-8")
            completed = subprocess.run(
                plan["analyze_command_argv"],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            self.assertEqual(completed.returncode, 3, completed.stderr)
            report = json.loads(Path(plan["analysis_output_json"]).read_text(encoding="utf-8"))
            self.assertEqual(report["gate"], "NO-GO")
            self.assertEqual(report["runtime_contract_audit"]["gate"], "NO-GO")
            self.assertTrue(
                any(
                    issue.startswith("blind_judge_semantic_load_failed:JSONDecodeError")
                    for issue in report["runtime_contract_audit"]["issues"]
                )
            )

    def test_analyze_cli_required_runtime_contract_go_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path, results, manifests, judge_path = _write_runtime_plan_fixture(root)
            output_json = root / "report.json"
            output_md = root / "report.md"
            command = [
                sys.executable,
                "tools/safe_loss_flip_rate_probe.py",
                "analyze",
            ]
            for result_path in results:
                command.extend(["--result", str(result_path)])
            command.extend(
                [
                    "--post-ids",
                    ",".join(_RUNTIME_AUDIT_POST_IDS),
                    "--repeats",
                    "5",
                    "--blind-judge",
                    str(judge_path),
                    "--run-plan",
                    str(plan_path),
                    "--require-runtime-contract",
                    "--output-json",
                    str(output_json),
                    "--output-md",
                    str(output_md),
                ]
            )
            completed = subprocess.run(
                command,
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(report["gate"], "GO")
            self.assertEqual(report["runtime_contract_audit"]["gate"], "GO")
            self.assertTrue(report["summary"]["all_independent_repeats_present"])
            self.assertTrue(report["summary"]["all_runtime_signatures_valid"])

            manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
            manifest["mcp_health_failure_count"] = 1
            manifests[0].write_text(json.dumps(manifest), encoding="utf-8")
            failed = subprocess.run(
                command,
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            self.assertEqual(failed.returncode, 3, failed.stderr)
            failed_report = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(failed_report["gate"], "NO-GO")
            self.assertFalse(failed_report["hard_hold_relaxation_allowed"])
            self.assertEqual(failed_report["runtime_contract_audit"]["gate"], "NO-GO")
            self.assertIn("Runtime plan 계약 감사", output_md.read_text(encoding="utf-8"))

    def test_load_rows_accepts_json_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text(json.dumps([_result_row(1, "safe_resolved")]), encoding="utf-8")

            rows = load_rows(path)

            self.assertEqual(rows[0]["post_id"], 1)

    def test_write_probe_input_outputs_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "probe.jsonl"
            write_probe_input([_input_row(1), _input_row(2)], path)

            lines = path.read_text(encoding="utf-8").splitlines()

            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["post_id"], 1)

    def test_independent_run_plan_preserves_n5_repeats_as_single_post_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp) / "probe_runs"
            post_ids = list(_N5_EXPECTED_POST_IDS)
            blind_judge = _write_bound_blind_judge(Path(tmp), post_ids)
            manifest, input_writes = build_independent_run_plan(
                source_rows=[_input_row(post_id) for post_id in post_ids],
                post_ids=post_ids,
                repeats=5,
                work_dir=work_dir,
                run_prefix="loop296_safe_loss_current_head",
                python_executable="python",
                expert_main=Path("expert_main.py"),
                parallel=16,
                expert_args=["--no-dashboard", "--reuse-shards-only"],
                blind_judge=blind_judge,
                run_plan_path=Path(tmp) / "plan.json",
            )

        self.assertTrue(manifest["minimum_repeats_contract_met"])
        self.assertEqual(manifest["expected_run_count"], 25)
        self.assertEqual(manifest["planned_run_count"], 25)
        for post_id in post_ids:
            self.assertEqual(manifest["repeat_count_by_post"][post_id], 5)
        self.assertEqual(len(input_writes), 25)
        self.assertEqual(len({str(path) for path, _row in input_writes}), 25)
        self.assertEqual(len({run["output_json"] for run in manifest["planned_runs"]}), 25)
        for input_path, row in input_writes:
            self.assertEqual(input_path.suffix, ".jsonl")
            self.assertNotIn("_flip_probe", row)
        for run in manifest["planned_runs"]:
            argv = run["command_argv"]
            self.assertIn("--input", argv)
            self.assertIn("--output", argv)
            self.assertNotIn("--no-dashboard", argv)
            self.assertIn("--reuse-shards-only", argv)
            self.assertIn("--llm-suspend-on-anomaly", argv)
            self.assertEqual(argv[argv.index("--llm-suspend-on-anomaly") + 1], "off")
            self.assertIn("--llm-suspend-threshold", argv)
            self.assertEqual(argv[argv.index("--llm-suspend-threshold") + 1], "0")
            self.assertIn("--llm-stream-first-token-timeout", argv)
            self.assertEqual(argv[argv.index("--llm-stream-first-token-timeout") + 1], "45")
            self.assertIn("--llm-stream-idle-timeout", argv)
            self.assertEqual(argv[argv.index("--llm-stream-idle-timeout") + 1], "45")
            self.assertEqual(argv[argv.index("--parallel") + 1], "16")
            self.assertIn("tools/attach_manifest_dashboard.py", run["attach_dashboard_command_line"])
        self.assertEqual(manifest["dashboard_contract"]["dashboard_policy"], "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS")
        self.assertEqual(manifest["stripped_forbidden_expert_args"], ["--no-dashboard"])
        self.assertEqual(
            manifest["noninteractive_watchdog_contract"],
            "background_probe_commands_disable_llm_suspend_prompt",
        )

    def test_independent_run_plan_flags_repeats_below_contract(self):
        post_ids = ["1", "2", "3", "4", "5"]
        with self.assertRaisesRegex(ValueError, "exactly five repeats"):
            build_independent_run_plan(
                source_rows=[_input_row(post_id) for post_id in post_ids],
                post_ids=post_ids,
                repeats=3,
                work_dir=Path("runs"),
                run_prefix="below_min",
                python_executable="python",
                expert_main=Path("expert_main.py"),
                minimum_repeats=5,
            )

    def test_independent_run_plan_rejects_non_n5_scope(self):
        with self.assertRaisesRegex(ValueError, "exactly five post_ids"):
            build_independent_run_plan(
                source_rows=[_input_row(post_id) for post_id in ("1", "2", "3", "4")],
                post_ids=["1", "2", "3", "4"],
                repeats=5,
                work_dir=Path("runs"),
                run_prefix="non-n5",
                python_executable="python",
                expert_main=Path("expert_main.py"),
                minimum_repeats=5,
            )


if __name__ == "__main__":
    unittest.main()
