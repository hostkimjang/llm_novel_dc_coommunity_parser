from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.grounding.research_local_benchmark import (
    DIAGNOSTIC_SCHEMA_VERSION,
    SCHEMA_VERSION,
    build_parallel_contract,
    effective_parallel,
    ensure_research_output_dir,
    load_and_validate_fixture,
    prompt_sha256,
    run_rows,
    sha256_file,
    sha256_value,
    summarize,
    validate_local_endpoint,
)


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _artifact_ref(path: Path) -> dict[str, Any]:
    return {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def _seal_manifest(manifest: dict[str, Any]) -> None:
    manifest.pop("manifest_sha256", None)
    manifest["manifest_sha256"] = sha256_value(manifest)


def _git_state() -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, check=False, capture_output=True, text=True).stdout.strip()

    return {"commit": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}


def _dependency_versions() -> dict[str, str]:
    values: dict[str, str] = {}
    for name in ("httpx", "pydantic", "fastapi", "uvicorn", "llama-cpp-python", "kiwipiepy"):
        try:
            values[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            values[name] = "UNAVAILABLE"
    return values


def _partition_for_input(path: Path) -> str:
    stem = path.stem.casefold()
    return "challenge" if "challenge" in stem else "baseline"


def _load_partitioned_fixture(path: Path) -> tuple[list[dict[str, Any]], str]:
    partition = _partition_for_input(path)
    rows = load_and_validate_fixture(path)
    return [
        {
            **row,
            "partition": str(row.get("partition") or partition),
        }
        for row in rows
    ], partition


def _dashboard_request(url: str, *, method: str = "GET", payload: Any = None) -> Any:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("DASHBOARD_INGEST_TOKEN", "").strip()
    if token:
        headers["X-Ingest-Token"] = token
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=5.0) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def _validate_dashboard_health(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("ok") is not True or payload.get("standalone") is not True:
        raise RuntimeError("standalone dashboard health contract failed")
    return payload


def _dashboard_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": payload.get("ok"),
        "standalone": payload.get("standalone"),
        "service": payload.get("service"),
        "pid": payload.get("pid"),
    }


def _dashboard_post(base_url: str, manifest: dict[str, Any]) -> None:
    status = {
        "batch_running": not manifest["large_run_complete"],
        "total_posts": manifest["job_count"],
        "current_index": manifest["completed_count"],
        "input_file": manifest["input_file"],
        "output_file": manifest["output_file"],
        "parallel_count": manifest["effective_parallel"],
        "batch_start_time": manifest["started_epoch"],
        "done_count": manifest["completed_count"],
        "relevant_count": 0,
        "noise_count": 0,
        "search_hits": 0,
        "search_misses": 0,
        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "post_summaries": [],
        "active_posts": {},
        "llm_suspended": False,
        "research_benchmark": {
            "run_id": manifest["run_id"],
            "claim_level": "RESEARCH_EVIDENCE_ONLY",
            "completed_count": manifest["completed_count"],
            "job_count": manifest["job_count"],
        },
    }
    _dashboard_request(
        f"{base_url.rstrip('/')}/api/ingest",
        method="POST",
        payload={"items": [{"kind": "status_snapshot", "data": status}]},
    )


def _report_markdown(manifest: dict[str, Any], metrics: dict[str, Any]) -> str:
    def metric_value(metric: Any) -> str:
        value = metric.get("value") if isinstance(metric, dict) else None
        return f"{value:.4f}" if isinstance(value, (int, float)) else "NOT_ESTIMABLE"

    def counts_value(values: Any) -> str:
        if not isinstance(values, dict):
            return "없음"
        return ", ".join(f"{key}={value}" for key, value in values.items() if value)

    lines = [
        "# 연구 전용 로컬 grounding 벤치마크 결과",
        "",
        f"- 판정: `{manifest['claim_level']}`",
        f"- namespace: `{manifest['namespace']}`",
        f"- 입력: `{manifest['benchmark_input_count']}`건 (합성/권리 메타데이터 검증 완료)",
        f"- 병렬도: requested `{manifest['requested_parallel']}`, effective `{manifest['effective_parallel']}`",
        f"- 대시보드: `{manifest['dashboard']['status']}` / `{manifest['dashboard']['url']}`",
        "- 중앙 Slang DB·production·publication 쓰기: `0`",
        "",
        "| arm | 분모 | 정답 | accuracy | terminal 상태 |",
        "|---|---:|---:|---:|---|",
    ]
    for arm, values in metrics["arms"].items():
        counts = ", ".join(f"{key}={value}" for key, value in values["terminal_status_counts"].items() if value)
        quality = (
            f"{values['accuracy']:.4f}"
            if values["accuracy"] is not None
            else f"NOT_ESTIMABLE (accounting {values['correct']}/{values['denominator']})"
        )
        lines.append(f"| {arm} | {values['denominator']} | {values['correct']} | {quality} | {counts} |")
    lines.extend(["", "## 진단"])
    for arm, values in metrics["arms"].items():
        recall = values.get("candidate_recall", {}).get("recall_at_5", {})
        conditional = values.get("conditional_selection", {})
        lines.append(
            f"- {arm}: Recall@5={metric_value(recall)}, 조건부 선택={metric_value(conditional)}"
        )
    lines.extend(
        [
            f"- case type: {counts_value(metrics.get('case_type_counts'))}",
            f"- failure stage: {counts_value(metrics.get('failure_stage_counts'))}",
            "Recall@K는 공통 BM25 후보 trace의 WORK truth에 대한 진단이며, 조건부 선택은 정답이 선택 후보에 포함된 WORK만 대상으로 한다.",
            "",
            "`ERROR`, `UNAVAILABLE`, `ABSTAIN`, `NIL`은 제거하지 않고 각 arm의 전체 입력 분모에 포함했다.",
            "이 결과는 연구 증거일 뿐 P0, production 또는 full-scan 승인 근거가 아니다.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="권리 안전 fixture용 연구 전용 로컬 LLM grounding 벤치마크")
    parser.add_argument("--input", default="tests/fixtures/research_local_benchmark_v1.jsonl")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--parallel", type=int, default=16)
    parser.add_argument("--dashboard-url", default="http://127.0.0.1:8080")
    parser.add_argument("--local-llm-endpoint")
    parser.add_argument("--local-llm-model")
    parser.add_argument("--local-llm-fingerprint", help="모델 weights SHA256 또는 별도 고정한 endpoint/model metadata SHA256")
    parser.add_argument(
        "--allow-configured-remote-vllm",
        action="store_true",
        help="expert_main에 이미 설정된 검증 대상 vLLM endpoint를 명시적으로 허용",
    )
    parser.add_argument("--timeout-sec", type=float, default=30.0)
    parser.add_argument("--seed", type=int, default=20260905)
    args = parser.parse_args()

    input_path = (ROOT / args.input).resolve() if not Path(args.input).is_absolute() else Path(args.input).resolve()
    output_dir = (ROOT / args.output_dir).resolve() if not Path(args.output_dir).is_absolute() else Path(args.output_dir).resolve()
    research_root = (ROOT / "out/research").resolve()
    try:
        output_dir = ensure_research_output_dir(output_dir, research_root)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    rows, partition = _load_partitioned_fixture(input_path)
    if args.parallel <= 0:
        raise SystemExit("--parallel must be positive")
    if len([value for value in (args.local_llm_endpoint, args.local_llm_model, args.local_llm_fingerprint) if value]) not in {0, 3}:
        raise SystemExit("local LLM endpoint, model, fingerprint must be provided together")
    if args.local_llm_fingerprint and (
        len(args.local_llm_fingerprint) != 64
        or any(character not in "0123456789abcdef" for character in args.local_llm_fingerprint.lower())
    ):
        raise SystemExit("--local-llm-fingerprint must be a SHA256 hex digest")
    if args.local_llm_endpoint:
        validate_local_endpoint(
            args.local_llm_endpoint,
            allow_configured_remote=args.allow_configured_remote_vllm,
        )
    dashboard_preflight = _validate_dashboard_health(
        _dashboard_request(f"{args.dashboard_url.rstrip('/')}/api/health")
    )
    output_dir.mkdir(parents=True)
    run_id = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_research_local")
    started_epoch = time.time()
    predictions_path = output_dir / "predictions.json"
    manifest_path = output_dir / "manifest.json"
    metrics_path = output_dir / "metrics.json"
    report_path = output_dir / "report_ko.md"
    parallel_contract = build_parallel_contract(args.parallel, len(rows))
    worker_count = parallel_contract["effective_parallel"]
    dashboard_preflight_receipt = _dashboard_receipt(dashboard_preflight)
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "namespace": "research.synthetic.offline_shadow",
        "claim_level": "RESEARCH_EVIDENCE_ONLY",
        "evidence_mode": "RESEARCH_GOLD_LITE",
        "publication_mode": "OFFLINE_SHADOW",
        "p0_authority_claimed": False,
        "production_authority_claimed": False,
        "full_scan_approval": False,
        "production_authority": False,
        "full_scan_authority": False,
        "publication_authority": False,
        "central_slang_db_write": False,
        "central_slang_db_writes": 0,
        "diagnostic_schema_version": DIAGNOSTIC_SCHEMA_VERSION,
        "partition": partition,
        "input_file": str(input_path),
        "output_file": str(predictions_path),
        "manifest_file": str(manifest_path),
        "benchmark_input_count": len(rows),
        "benchmark_input_counts_by_partition": {partition: len(rows)},
        "input_post_count": len(rows) * 4,
        "job_count": len(rows) * 4,
        "completed_count": 0,
        "failed_count": 0,
        "large_run_complete": False,
        **parallel_contract,
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "started_epoch": started_epoch,
        "seed": args.seed,
        "config": {
            "requested_parallel": args.parallel,
            "timeout_sec": args.timeout_sec,
            "seed": args.seed,
            "diagnostic_schema_version": DIAGNOSTIC_SCHEMA_VERSION,
            "partition": partition,
            "arms": ["lexical_baseline", "bm25_fixture_corpus_retriever", "bm25_reranker_nil", "local_llm"],
            "task_scope": "FIXTURE_CORPUS_RETRIEVAL_NOT_EXTERNAL_OPEN_CORPUS",
            "local_llm_endpoint_scope": (
                "CONFIGURED_REMOTE_VLLM" if args.allow_configured_remote_vllm else "LOOPBACK_ONLY"
            ),
        },
        "fingerprints": {
            "input_sha256": sha256_file(input_path),
            "gold_projection_sha256": sha256_value(
                [
                    {
                        "query_id": row["query_id"],
                        "gold_label": row["gold_label"],
                        "case_type": row.get("case_type"),
                        "expected_action": row.get("expected_action"),
                        "partition": row.get("partition"),
                    }
                    for row in rows
                ]
            ),
            "prompt_sha256": prompt_sha256(),
            "runner_sha256": sha256_file(Path(__file__).resolve()),
            "implementation_sha256": sha256_file(ROOT / "src/llm_batch/grounding/research_local_benchmark.py"),
            "pyproject_sha256": sha256_file(ROOT / "pyproject.toml"),
        },
        "git": _git_state(),
        "runtime": {"python": sys.version, "platform": platform.platform(), "dependencies": _dependency_versions()},
        "models": {
            "lexical_baseline": "research.lexical-baseline.v1",
            "bm25_fixture_corpus_retriever": "research.bm25-pure-python.v1",
            "bm25_reranker_nil": "research.lexical-reranker-nil.v1",
            "local_llm": args.local_llm_model or "UNAVAILABLE_MODEL_IDENTITY",
            "local_llm_endpoint_sha256": sha256_value(args.local_llm_endpoint) if args.local_llm_endpoint else None,
            "local_llm_identity_fingerprint": args.local_llm_fingerprint,
            "local_llm_endpoint_scope": (
                "CONFIGURED_REMOTE_VLLM" if args.allow_configured_remote_vllm else "LOOPBACK_ONLY"
            ),
        },
        "gold_lite": {
            "policy": "SINGLE_CURATOR_WITH_BOUNDED_BLIND_RECHECK",
            "blind_recheck_count": sum(row.get("blind_recheck") is not None for row in rows),
            "blind_recheck_max": max(1, (len(rows) + 3) // 4),
        },
        "rights": {
            "allowed_kinds": sorted({row["rights"]["kind"] for row in rows}),
            "source_and_retention_recorded": True,
        },
        "dashboard": {
            "enabled": True,
            "url": args.dashboard_url,
            "status": "CONNECTED",
            "preflight_receipt": dashboard_preflight_receipt,
            "preflight_response_sha256": sha256_value(dashboard_preflight_receipt),
        },
    }
    manifest["fingerprints"]["config_sha256"] = sha256_value(manifest["config"])
    _write_json(manifest_path, manifest)
    _dashboard_post(args.dashboard_url, manifest)

    last_dashboard_update = 0

    def progress(completed: int, total: int) -> None:
        nonlocal last_dashboard_update
        manifest["completed_count"] = completed
        if completed == total or completed - last_dashboard_update >= max(1, total // 8):
            _write_json(manifest_path, manifest)
            _dashboard_post(args.dashboard_url, manifest)
            last_dashboard_update = completed

    predictions = run_rows(
        rows,
        requested_parallel=args.parallel,
        local_llm_endpoint=args.local_llm_endpoint,
        local_llm_model=args.local_llm_model,
        timeout_sec=args.timeout_sec,
        seed=args.seed,
        progress=progress,
        allow_configured_remote=args.allow_configured_remote_vllm,
    )
    metrics = summarize(predictions)
    metrics["throughput"] = {
        "accounted_predictions_per_sec": len(predictions) / max(time.time() - started_epoch, 1e-9),
        "accounted_predictions": len(predictions),
    }
    _write_json(predictions_path, predictions)
    _write_json(metrics_path, metrics)
    report_path.write_text(_report_markdown(manifest, metrics), encoding="utf-8", newline="\n")
    manifest.update(
        {
            "completed_count": len(predictions),
            "failed_count": sum(item["terminal_status"] == "ERROR" for item in predictions),
            "terminal_status_counts": {
                status: sum(item["terminal_status"] == status for item in predictions)
                for status in ("RESOLVED", "NIL", "ABSTAIN", "UNAVAILABLE", "ERROR")
            },
            "per_arm_accounting": {
                arm: {
                    "denominator": values["denominator"],
                    "evaluable_denominator": values["evaluable_only_accuracy"]["denominator"],
                    "terminal_status_counts": values["terminal_status_counts"],
                }
                for arm, values in metrics["arms"].items()
            },
            "large_run_complete": True,
            "ended_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "duration_sec": round(time.time() - started_epoch, 6),
            "artifacts": {
                "input": _artifact_ref(input_path),
                "predictions": _artifact_ref(predictions_path),
                "metrics": _artifact_ref(metrics_path),
                "report_ko": _artifact_ref(report_path),
            },
            "metrics_sha256": sha256_value(metrics),
            "semantic_output_sha256": sha256_value(
                [
                    {key: value for key, value in item.items() if key != "latency_ms"}
                    for item in predictions
                ]
            ),
        }
    )
    dashboard_postflight_receipt = _dashboard_receipt(
        _validate_dashboard_health(_dashboard_request(f"{args.dashboard_url.rstrip('/')}/api/health"))
    )
    manifest["dashboard"]["postflight_receipt"] = dashboard_postflight_receipt
    manifest["dashboard"]["postflight_response_sha256"] = sha256_value(dashboard_postflight_receipt)
    _seal_manifest(manifest)
    _write_json(manifest_path, manifest)
    _dashboard_post(args.dashboard_url, manifest)
    print(json.dumps({"manifest": str(manifest_path), "metrics": metrics}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
