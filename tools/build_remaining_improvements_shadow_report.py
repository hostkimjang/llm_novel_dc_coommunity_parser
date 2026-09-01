#!/usr/bin/env python3
"""Build the frozen-2,712 BEFORE/SHADOW-AFTER analytical artifacts.

This is a reporting tool.  It validates exact post_id joins and receipt
non-interference, then writes a paired JSONL, an executed notebook, and the
canonical Data Analytics portable-report input.  It never calls the LLM,
search, dashboard, publication WAL writer, or recovery activation path.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

import nbformat
from nbclient import NotebookClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.llm_batch.ledger.publication_commit import validate_publication_result_commit
from src.llm_batch.measurement.semantic_recovery_plan import (
    validate_semantic_recovery_plan_receipt,
)
from src.llm_batch.measurement.semantic_review_router import (
    validate_semantic_review_router_receipt,
)


DEFAULT_BASE = REPO_ROOT / "out/regression_safe_2712_remaining_improvements_20260718"
DEFAULT_DOCS = REPO_ROOT / "docs/devs"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        rows.append(value)
    return rows


def _post_id(value: Any) -> str:
    text = str(value).strip()
    if not text.isdigit():
        raise ValueError(f"invalid post_id: {value!r}")
    return text


def _index_unique(rows: Iterable[Mapping[str, Any]], *, source: str) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        key = _post_id(row.get("post_id"))
        if key in indexed:
            raise ValueError(f"duplicate post_id in {source}: {key}")
        indexed[key] = row
    return indexed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _source(
    source_id: str,
    label: str,
    path: Path,
    description: str,
    *,
    tables: list[str],
) -> dict[str, Any]:
    return {
        "id": source_id,
        "label": label,
        "path": _relative(path),
        "query": {
            "engine": "sqlite",
            "language": "sql",
            "sql": "SELECT * FROM source_rows",
            "description": description,
            "tables_used": tables,
            "filters": ["exact post_id join", "frozen labels joined only after receipt production"],
            "metric_definitions": ["majority=2-of-3", "systematic=majority transition", "any-run=at least one of three"],
        },
    }


def _build_notebook(
    *,
    notebook_path: Path,
    paired_path: Path,
    router_summary_path: Path,
    plan_summary_path: Path,
    grouped_report_path: Path,
) -> None:
    rel_paired = _relative(paired_path)
    rel_router = _relative(router_summary_path)
    rel_plan = _relative(plan_summary_path)
    rel_grouped = _relative(grouped_report_path)
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    nb.metadata["language_info"] = {"name": "python", "version": "3.12"}
    nb.cells = [
        nbformat.v4.new_markdown_cell(
            "# 동결 2,712행 남은 개선 BEFORE/SHADOW-AFTER\n\n"
            "공개 비간섭, review-router, P1 plan-only, 32행×3회 grouped 관측을 분리 검증한다."
        ),
        nbformat.v4.new_code_cell(
            "from pathlib import Path\nimport json\nfrom collections import Counter\n"
            "ROOT=Path.cwd()\n"
            f"PAIRED=ROOT/{rel_paired!r}\n"
            f"ROUTER=ROOT/{rel_router!r}\n"
            f"PLAN=ROOT/{rel_plan!r}\n"
            f"GROUPED=ROOT/{rel_grouped!r}\n"
            "paired=[json.loads(x) for x in PAIRED.read_text(encoding='utf-8').splitlines() if x.strip()]\n"
            "router=json.loads(ROUTER.read_text(encoding='utf-8'))\n"
            "plan=json.loads(PLAN.read_text(encoding='utf-8'))\n"
            "grouped=json.loads(GROUPED.read_text(encoding='utf-8'))\n"
            "len(paired), grouped['pairing']"
        ),
        nbformat.v4.new_code_cell(
            "ids=[r['post_id'] for r in paired]\n"
            "assert len(ids)==2712 and len(set(ids))==2712\n"
            "assert all(r['noninterference']['decision_id_equal'] and r['noninterference']['stable_result_sha256_equal'] and r['noninterference']['public_projection_sha256_equal'] for r in paired)\n"
            "assert all(not r['shadow_after']['router_public_apply'] and not r['shadow_after']['plan_public_apply'] for r in paired)\n"
            "{'rows':len(ids),'unique':len(set(ids)),'public_drift':0,'public_apply_true':0}"
        ),
        nbformat.v4.new_code_cell(
            "router_metrics=router['offline_evaluation_only']['metrics']\n"
            "{k:router_metrics[k] for k in ['high_risk_union','published_intervention','fn_title_missing','fp_non_novel','wrong_work','multiwork','pass','safe_no_title','ultra_safe_no_title']}"
        ),
        nbformat.v4.new_code_cell(
            "{'state_counts':plan['plan']['state_counts'], 'canonical_binding_rows':plan['plan']['canonical_binding_rows'], 'raw_ocr_rows':plan['plan']['raw_ocr_evidence_rows'], 'search_calls':plan['plan']['search_calls_executed'], 'network_calls':plan['plan']['network_calls_executed']}"
        ),
        nbformat.v4.new_code_cell(
            "q=grouped['metrics']['quality']\n"
            "summary={k:{arm:q[k][arm][field] for arm in ('before','after')} for k,field in [('correct_title_recovery','majority_posts'),('false_positive','majority_posts'),('hold_integrity','majority_posts'),('pass_retention','majority_posts'),('unsafe_publish','any_run_posts'),('wrong_work_unrecovered','majority_posts')]}\n"
            "summary"
        ),
        nbformat.v4.new_code_cell(
            "{'measurement_gate':grouped['measurement_gate'], 'semantic_auto_activation_gate':grouped['semantic_auto_activation_gate'], 'gate_reasons':grouped['gate_reasons'], 'full_scan_approval':False}"
        ),
    ]
    client = NotebookClient(nb, timeout=180, kernel_name="python3", resources={"metadata": {"path": str(REPO_ROOT)}})
    client.execute()
    notebook_path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, notebook_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--docs", type=Path, default=DEFAULT_DOCS)
    args = parser.parse_args()
    base = args.base.resolve()
    docs = args.docs.resolve()

    ledger_path = REPO_ROOT / "out/live_combined_row_review_20260715_143806_848671_2712_20260716/final_2712_row_adjudication_ledger.jsonl"
    checkpoint_path = REPO_ROOT / "out/expert_result_20260715_143806_848671_checkpoint.jsonl"
    router_summary_path = base / "semantic_review_router_frozen2712_replay/summary.json"
    router_rows_path = base / "semantic_review_router_frozen2712_replay/rows.jsonl"
    plan_summary_path = base / "semantic_recovery_plan_frozen2712_replay/summary.json"
    plan_rows_path = base / "semantic_recovery_plan_frozen2712_replay/rows.jsonl"
    replay_path = base / "release_candidate_frozen2712_replay/publish_contract_replay_summary.json"
    canary_path = base / "release_candidate_canary_post11718115_v2/summary.json"
    grouped_path = base / "release_candidate_grouped_ab_v1/grouped_analysis/report.json"
    grouped_transitions_path = base / "release_candidate_grouped_ab_v1/grouped_analysis/transitions.jsonl"

    ledger_rows = _read_jsonl(ledger_path)
    checkpoint_rows = _read_jsonl(checkpoint_path)
    router_rows = _read_jsonl(router_rows_path)
    plan_rows = _read_jsonl(plan_rows_path)
    ledger = _index_unique(ledger_rows, source="ledger")
    checkpoint = _index_unique(checkpoint_rows, source="checkpoint")
    router = _index_unique(router_rows, source="router")
    plan = _index_unique(plan_rows, source="plan")
    expected_ids = set(ledger)
    if len(expected_ids) != 2712 or set(router) != expected_ids or set(plan) != expected_ids:
        raise ValueError("ledger/router/plan exact post_id join failed")
    if expected_ids - set(checkpoint):
        raise ValueError("checkpoint is missing ledger post_ids")

    paired_rows: list[dict[str, Any]] = []
    for post_id, ledger_row in sorted(ledger.items(), key=lambda item: int(item[0])):
        checkpoint_row = checkpoint[post_id]
        result = checkpoint_row.get("result")
        commit = checkpoint_row.get("publication_commit")
        if not isinstance(result, Mapping) or not isinstance(commit, Mapping):
            raise ValueError(f"checkpoint row missing result/commit: {post_id}")
        validate_publication_result_commit(result, commit, expected_post_id=int(post_id))
        router_row = router[post_id]
        plan_row = plan[post_id]
        router_receipt = router_row.get("router", {}).get("receipt")
        plan_receipt = plan_row.get("plan_receipt")
        router_receipt = validate_semantic_review_router_receipt(router_receipt, expected_post_id=int(post_id))
        plan_receipt = validate_semantic_recovery_plan_receipt(plan_receipt, expected_post_id=int(post_id))
        if router_receipt["publication_decision_id"] != commit["decision_id"]:
            raise ValueError(f"router publication binding mismatch: {post_id}")
        if plan_receipt["publication_decision_id"] != commit["decision_id"]:
            raise ValueError(f"plan publication binding mismatch: {post_id}")
        router_non = router_row.get("noninterference", {})
        plan_non = plan_row.get("noninterference", {})
        for field in ("decision_id_equal", "stable_result_sha256_equal", "public_projection_sha256_equal"):
            if router_non.get(field) is not True or plan_non.get(field) is not True:
                raise ValueError(f"noninterference failed for {post_id}: {field}")
        independent = ledger_row.get("independent_semantic_verdict") or {}
        offline = router_row.get("offline_evaluation") or {}
        plan_value = plan_receipt["plan"]
        paired_rows.append(
            {
                "post_id": post_id,
                "frozen": {
                    "review_verdict": independent.get("review_verdict"),
                    "dashboard_action": independent.get("dashboard_action"),
                    "severity": ledger_row.get("severity"),
                    "cohorts": offline.get("cohorts") or [],
                },
                "before": {
                    "publication_decision_id": commit["decision_id"],
                    "outcome": commit["outcome"],
                    "publish_allowed": commit["publish_allowed"],
                    "stable_result_sha256": commit["stable_result_sha256"],
                    "public_projection_sha256": commit["public_projection_sha256"],
                },
                "shadow_after": {
                    "router_state": router_receipt["state"],
                    "router_trigger_codes": router_receipt["trigger_codes"],
                    "router_public_apply": router_receipt["public_apply"],
                    "plan_state": plan_value["state"],
                    "plan_blocker_codes": plan_value["blocker_codes"],
                    "plan_public_apply": plan_receipt["public_apply"],
                    "media_action": plan_value["media_action"],
                    "relationship_counts": plan_value["relationship_counts"],
                    "canonical_binding_count": len(plan_value["canonical_bindings"]),
                    "raw_ocr_evidence_count": plan_value["raw_ocr_evidence_count"],
                    "query_execution_allowed": plan_value["query_plan"]["query_execution_allowed"],
                    "planned_query_budget": plan_value["query_plan"]["max_queries"],
                    "search_calls_executed": plan_value["search_calls_executed"],
                    "network_calls_executed": plan_value["network_calls_executed"],
                },
                "noninterference": {
                    "decision_id_equal": True,
                    "stable_result_sha256_equal": True,
                    "public_projection_sha256_equal": True,
                },
                "actual_effect": {"status": "NOT_ESTIMABLE_SHADOW_ONLY"},
            }
        )

    paired_path = docs / "LIVE_RUN_2712_REMAINING_IMPROVEMENTS_BEFORE_SHADOW_AFTER_PAIRED_20260718.jsonl"
    notebook_path = docs / "LIVE_RUN_2712_REMAINING_IMPROVEMENTS_BEFORE_SHADOW_AFTER_ANALYSIS_20260718.ipynb"
    artifact_path = docs / "LIVE_RUN_2712_REMAINING_IMPROVEMENTS_BEFORE_SHADOW_AFTER_ARTIFACT_20260718.json"
    _write_jsonl(paired_path, paired_rows)

    _build_notebook(
        notebook_path=notebook_path,
        paired_path=paired_path,
        router_summary_path=router_summary_path,
        plan_summary_path=plan_summary_path,
        grouped_report_path=grouped_path,
    )

    router_summary = _read_json(router_summary_path)
    plan_summary = _read_json(plan_summary_path)
    replay = _read_json(replay_path)
    canary = _read_json(canary_path)
    grouped = _read_json(grouped_path)
    transitions = _read_jsonl(grouped_transitions_path)
    q = grouped["metrics"]["quality"]
    router_metrics = router_summary["offline_evaluation_only"]["metrics"]
    plan_metrics = plan_summary["offline_evaluation_only"]["cohort"]

    router_rates = []
    router_labels = {
        "high_risk_union": "고위험 union",
        "published_intervention": "공개 개입 35",
        "fn_title_missing": "FN title missing",
        "fp_non_novel": "FP non-novel",
        "wrong_work": "WRONG_WORK",
        "multiwork": "multiwork",
        "pass": "PASS (오검토)",
        "safe_no_title": "정상 no-title (오검토)",
        "ultra_safe_no_title": "초저위험 (오검토)",
    }
    for key, label in router_labels.items():
        metric = router_metrics[key]
        router_rates.append(
            {
                "cohort": label,
                "kind": "collateral_false_review" if key in {"pass", "safe_no_title", "ultra_safe_no_title"} else "risk_recall",
                "numerator": metric["routed"],
                "denominator": metric["denominator"],
                "rate_pct": round(metric["rate"] * 100, 1),
            }
        )

    plan_hold = []
    for key, label in router_labels.items():
        if key not in plan_metrics:
            continue
        metric = plan_metrics[key]
        hold = int(metric["plan_state_counts"].get("HOLD", 0))
        denominator = int(metric["denominator"])
        plan_hold.append(
            {"cohort": label, "hold": hold, "denominator": denominator, "rate_pct": round(_rate(hold, denominator) * 100, 1)}
        )

    grouped_quality = []
    grouped_metric_specs = [
        ("majority compliance", "adjudication", "compliant_posts"),
        ("correct title recovery", "correct_title_recovery", "majority_posts"),
        ("FP", "false_positive", "majority_posts"),
        ("HOLD integrity", "hold_integrity", "majority_posts"),
        ("PASS retention", "pass_retention", "majority_posts"),
        ("unsafe any-run", "unsafe_publish", "any_run_posts"),
        ("wrong-work unrecovered", "wrong_work_unrecovered", "majority_posts"),
    ]
    for label, key, field in grouped_metric_specs:
        for arm in ("before", "after"):
            if key == "adjudication":
                value = grouped["metrics"]["adjudication_majority_compliance"][arm][field]
            else:
                value = q[key][arm][field]
            grouped_quality.append({"metric": label, "arm": arm.upper(), "value": value})

    examples: list[dict[str, Any]] = []
    for row in transitions:
        before = row["before"]
        after = row["after"]
        verdict = row["frozen_review"]["review_verdict"]
        category = None
        if (not before["quality"]["correct_title_recovery"]["majority"] and after["quality"]["correct_title_recovery"]["majority"]):
            category = "개선"
        elif (not before["quality"]["unsafe_publish"]["any_run"] and after["quality"]["unsafe_publish"]["any_run"]):
            category = "새 악화(단발)"
        elif verdict == "PASS" and after["quality"]["pass_retention"]["exact_run_count"] != before["quality"]["pass_retention"]["exact_run_count"]:
            category = "정상행 변동"
        elif after["quality"]["wrong_work_unrecovered"]["majority"]:
            category = "미해결"
        elif (not before["modal_projection"]["unanimous"] or not after["modal_projection"]["unanimous"]):
            category = "변동성 보류"
        if category is None:
            continue
        examples.append(
            {
                "category": category,
                "post_id": row["post_id"],
                "verdict": verdict,
                "expected": row["frozen_review"].get("expected_public_title"),
                "before": f"{before['exact_adjudication_compliant_count']}/3 compliant; {before['modal_projection']['fraction_label']}",
                "after": f"{after['exact_adjudication_compliant_count']}/3 compliant; {after['modal_projection']['fraction_label']}",
                "disposition": "자동 활성화 금지; 반복/정본 근거 보존",
            }
        )
    category_order = {"개선": 0, "새 악화(단발)": 1, "정상행 변동": 2, "미해결": 3, "변동성 보류": 4}
    examples = sorted(examples, key=lambda row: (category_order[row["category"]], int(row["post_id"])))[:14]

    source_paths = [
        ("ledger", ledger_path, len(ledger_rows), len(ledger), 0, 0),
        ("checkpoint", checkpoint_path, len(checkpoint_rows), len(checkpoint), len(expected_ids - set(checkpoint)), len(set(checkpoint) - expected_ids)),
        ("router", router_rows_path, len(router_rows), len(router), len(expected_ids - set(router)), len(set(router) - expected_ids)),
        ("plan", plan_rows_path, len(plan_rows), len(plan), len(expected_ids - set(plan)), len(set(plan) - expected_ids)),
        ("paired", paired_path, len(paired_rows), len({_post_id(row['post_id']) for row in paired_rows}), 0, 0),
        ("grouped transitions", grouped_transitions_path, len(transitions), len({_post_id(row['post_id']) for row in transitions}), 0, 0),
    ]
    source_integrity = [
        {
            "source": label,
            "path": _relative(path),
            "sha256": _sha256(path),
            "rows": rows,
            "unique_post_ids": unique,
            "missing": missing,
            "extra": extra,
        }
        for label, path, rows, unique, missing, extra in source_paths
    ]

    gate_matrix = [
        {"rank": 1, "gate": "2,712 exact join/receipt", "status": "GO", "evidence": "2,712/2,712; duplicate/missing 0"},
        {"rank": 2, "gate": "public noninterference", "status": "GO", "evidence": "decision/stable/projection drift 0; public_apply=true 0"},
        {"rank": 3, "gate": "release-candidate canary", "status": canary["status"], "evidence": "runtime/measurement/noninterference GO; release fingerprint match"},
        {"rank": 4, "gate": "grouped runtime/comparability", "status": "GO", "evidence": "6/6 runtime GO; exact 32×3×2; dashboard/parallel 16"},
        {"rank": 5, "gate": "grouped call measurement", "status": grouped["measurement_gate"], "evidence": "4/6 GO; two unlinked/estimated rows"},
        {"rank": 6, "gate": "review router", "status": "NO_GO", "evidence": "high-risk recall 74.2%; normal false-review 20.0%"},
        {"rank": 7, "gate": "P1 recovery plan", "status": "PLAN_ONLY / NO_GO", "evidence": "receipt 192/192; public apply/calls 0; effectiveness unproven"},
        {"rank": 8, "gate": "search quality", "status": "NO_GO", "evidence": "AFTER SEARCH_DEGRADED 51/96; unknown 0"},
        {"rank": 9, "gate": "semantic auto activation", "status": grouped["semantic_auto_activation_gate"], "evidence": ", ".join(grouped["gate_reasons"])},
        {"rank": 10, "gate": "P2 ultra-safe early route", "status": "NOT_RUN / NO_GO", "evidence": "measurement/search/router hard prerequisites not green"},
        {"rank": 11, "gate": "full_scan_approval", "status": "false", "evidence": "targeted shadow/grouped evidence only"},
    ]

    sources = [
        _source("router_source", "2,712 review-router replay", router_summary_path, "위험군 recall과 정상군 false-review", tables=["summary.json", "rows.jsonl"]),
        _source("plan_source", "2,712 P1 plan replay", plan_summary_path, "HOLD·canonical binding·OCR·query plan", tables=["summary.json", "rows.jsonl"]),
        _source("grouped_source", "32행×3회 BEFORE/SHADOW-AFTER", grouped_path, "반복 consensus·variance·search·cost", tables=["report.json", "transitions.jsonl"]),
        _source("paired_source", "2,712 exact paired table", paired_path, "공개 비간섭과 attempt-local receipt exact join", tables=["paired JSONL"]),
        _source("replay_source", "release-candidate persisted replay", replay_path, "공개 계약 deterministic regression", tables=["publish_contract_replay_summary.json"]),
    ]

    generated = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
    title = "동결 2,712행 남은 개선: BEFORE 대비 SHADOW-AFTER 기술 검증"
    artifact = {
        "surface": "report",
        "manifest": {
            "version": 1,
            "surface": "report",
            "title": title,
            "description": "공개 비간섭 개선과 실제 의미 효과 미승인을 분리한 2,712행·32행×3회 기술 보고서",
            "generatedAt": generated,
            "blocks": [
                {"id": "title", "type": "markdown", "body": f"# {title}"},
                {"id": "summary", "type": "markdown", "body": "## 결론\n\n구현·receipt 무결성·공개 비간섭은 GO다. 그러나 실제 자동 recovery와 P2는 NO-GO다. 32행×3회에서 majority compliance는 17→18, correct title majority는 0→1이었지만, measurement 4/6만 GO, router recall 74.2%, 정상 false-review 20.0%, search degraded, WRONG_WORK 3/3 미회복, PASS retention 1/2 때문에 기존 정답 무변경 원칙을 해제하지 않는다."},
                {"id": "headline_metrics", "type": "metric-strip", "cardIds": ["join_card", "drift_card", "majority_card", "full_scan_card"]},
                {"id": "gate_heading", "type": "markdown", "body": "## GO/NO-GO 매트릭스\n\nRuntime, measurement, search, semantic quality, full scan을 분리했다."},
                {"id": "gate_table_block", "type": "table", "tableId": "gate_table"},
                {"id": "grouped_heading", "type": "markdown", "body": "## 32행×3회 실제 grouped 관측\n\nAFTER는 sidecar를 실제 공개 적용한 인과 arm이 아니라 fresh SHADOW-AFTER다. 막대는 정본 대비 반복 consensus 또는 any-run 수를 보여준다."},
                {"id": "grouped_chart_block", "type": "chart", "chartId": "grouped_chart"},
                {"id": "examples_heading", "type": "markdown", "body": "## 개선·악화·변동성 보류 사례\n\n한 번의 흔들림은 자동 rollback 근거가 아니며, 반복 합의와 정본 기준으로 분류했다."},
                {"id": "examples_table_block", "type": "table", "tableId": "examples_table"},
                {"id": "router_heading", "type": "markdown", "body": "## Review router는 관측 가능해졌지만 승인 임계치 미달\n\n위험군 recall과 정상군 false-review를 같은 분모 정의로 따로 표시한다. cohort는 중첩되므로 합산하지 않는다."},
                {"id": "router_chart_block", "type": "chart", "chartId": "router_chart"},
                {"id": "plan_heading", "type": "markdown", "body": "## P1 plan-only는 안전하게 봉인됐지만 collateral HOLD가 크다\n\n계획은 search/network를 실행하지 않고 공개 결과를 바꾸지 않는다. HOLD 비율은 실제 개선률이 아니다."},
                {"id": "plan_chart_block", "type": "chart", "chartId": "plan_chart"},
                {"id": "integrity_heading", "type": "markdown", "body": "## Exact join과 source 무결성\n\n2,712행 paired JSONL이 정본이다. frozen label은 receipt를 생성한 뒤에만 결합했다."},
                {"id": "integrity_table_block", "type": "table", "tableId": "integrity_table"},
                {"id": "limits", "type": "markdown", "body": "## 한계와 다음 경계\n\nDirect OCR은 canonical identity fail-close까지만 구현됐고 producer lineage가 68→79 events로 갈라진다. typed media evidence가 persisted source view에 없어 media quarantine 효과는 미측정이다. P2 188건은 measurement/search/router가 모두 green이 아니므로 실행하지 않았다. 정확한 GPT-5.6 Sol + Pro lane은 recovery_required에서 중복 제출하지 않았고 새 검증 답변이 없어 로컬 근거로 사용하지 않았다. 104,502행 run은 읽기 전용이며 이 보고서는 full scan 승인이 아니다."},
            ],
            "cards": [
                {"id": "join_card", "dataset": "headline", "sourceId": "paired_source", "description": "ledger/router/plan exact join", "metrics": [{"label": "exact paired rows", "field": "paired_rows", "format": "number"}]},
                {"id": "drift_card", "dataset": "headline", "sourceId": "paired_source", "description": "공개 decision/stable/projection drift", "metrics": [{"label": "public drift", "field": "public_drift", "format": "number"}]},
                {"id": "majority_card", "dataset": "headline", "sourceId": "grouped_source", "description": "32행 majority compliance AFTER-BEFORE", "metrics": [{"label": "majority delta", "field": "majority_delta", "format": "number"}]},
                {"id": "full_scan_card", "dataset": "headline", "sourceId": "replay_source", "description": "0=false; targeted 결과를 전체 승인으로 승격하지 않음", "metrics": [{"label": "full_scan_approval", "field": "full_scan_numeric", "format": "number"}]},
            ],
            "charts": [
                {"id": "grouped_chart", "title": "32행×3회 품질 지표", "subtitle": "majority 또는 any-run 수; 지표별 분모가 다름", "type": "bar", "dataset": "grouped_quality", "sourceId": "grouped_source", "options": {"orientation": "vertical", "grouping": "grouped"}, "encodings": {"x": {"field": "metric", "type": "nominal", "label": "지표"}, "y": {"field": "value", "type": "quantitative", "label": "post_id 수", "format": "number"}, "color": {"field": "arm", "type": "nominal", "label": "arm"}, "tooltip": [{"field": "metric", "type": "nominal"}, {"field": "arm", "type": "nominal"}, {"field": "value", "type": "quantitative", "format": "number"}]}},
                {"id": "router_chart", "title": "cohort별 review-router 비율", "subtitle": "위험군은 recall, 정상군은 false-review; 목표는 각각 100%와 0%", "type": "bar", "dataset": "router_rates", "sourceId": "router_source", "options": {"orientation": "vertical", "grouping": "grouped"}, "encodings": {"x": {"field": "cohort", "type": "nominal", "label": "cohort"}, "y": {"field": "rate_pct", "type": "quantitative", "label": "비율(%)", "format": "number"}, "color": {"field": "kind", "type": "nominal", "label": "해석"}, "tooltip": [{"field": "numerator", "type": "quantitative", "format": "number"}, {"field": "denominator", "type": "quantitative", "format": "number"}, {"field": "rate_pct", "type": "quantitative", "format": "number"}]}},
                {"id": "plan_chart", "title": "P1 plan-only HOLD 비율", "subtitle": "위험군과 collateral 대조군; 실제 recovery 효과가 아님", "type": "bar", "dataset": "plan_hold", "sourceId": "plan_source", "options": {"orientation": "vertical"}, "encodings": {"x": {"field": "cohort", "type": "nominal", "label": "cohort"}, "y": {"field": "rate_pct", "type": "quantitative", "label": "HOLD 비율(%)", "format": "number"}, "tooltip": [{"field": "hold", "type": "quantitative", "format": "number"}, {"field": "denominator", "type": "quantitative", "format": "number"}, {"field": "rate_pct", "type": "quantitative", "format": "number"}]}},
            ],
            "tables": [
                {"id": "gate_table", "title": "게이트 매트릭스", "subtitle": "runtime·measurement·search·semantic·full scan 분리", "dataset": "gate_matrix", "sourceId": "grouped_source", "defaultSort": {"field": "rank", "direction": "asc"}, "columns": [{"field": "rank", "label": "순서", "type": "number", "format": "number"}, {"field": "gate", "label": "게이트", "type": "text"}, {"field": "status", "label": "상태", "type": "text"}, {"field": "evidence", "label": "근거", "type": "text"}]},
                {"id": "examples_table", "title": "post_id exact 주요 사례", "subtitle": "개선·새 악화·정상행 변동·미해결·variance hold", "dataset": "examples", "sourceId": "grouped_source", "columns": [{"field": "category", "label": "분류", "type": "text"}, {"field": "post_id", "label": "post_id", "type": "text"}, {"field": "verdict", "label": "정본", "type": "text"}, {"field": "expected", "label": "기대 제목", "type": "text"}, {"field": "before", "label": "BEFORE", "type": "text"}, {"field": "after", "label": "SHADOW-AFTER", "type": "text"}, {"field": "disposition", "label": "조치", "type": "text"}]},
                {"id": "integrity_table", "title": "source 무결성", "subtitle": "행·고유 ID·누락·extra·SHA-256", "dataset": "source_integrity", "sourceId": "paired_source", "columns": [{"field": "source", "label": "source", "type": "text"}, {"field": "path", "label": "path", "type": "text"}, {"field": "sha256", "label": "SHA-256", "type": "text"}, {"field": "rows", "label": "rows", "type": "number", "format": "number"}, {"field": "unique_post_ids", "label": "unique", "type": "number", "format": "number"}, {"field": "missing", "label": "missing", "type": "number", "format": "number"}, {"field": "extra", "label": "extra", "type": "number", "format": "number"}]},
            ],
            "sources": sources,
        },
        "snapshot": {
            "version": 1,
            "status": "ready",
            "generatedAt": generated,
            "datasets": {
                "headline": [{"paired_rows": 2712, "public_drift": 0, "majority_delta": grouped["metrics"]["adjudication_majority_compliance"]["after"]["compliant_posts"] - grouped["metrics"]["adjudication_majority_compliance"]["before"]["compliant_posts"], "full_scan_numeric": 0}],
                "gate_matrix": gate_matrix,
                "grouped_quality": grouped_quality,
                "router_rates": router_rates,
                "plan_hold": plan_hold,
                "examples": examples,
                "source_integrity": source_integrity,
            },
        },
        "sources": sources,
    }
    _write_json(artifact_path, artifact)
    print(json.dumps({"status": "GO_ARTIFACT_INPUT", "paired": _relative(paired_path), "notebook": _relative(notebook_path), "artifact": _relative(artifact_path), "paired_sha256": _sha256(paired_path), "artifact_sha256": _sha256(artifact_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
