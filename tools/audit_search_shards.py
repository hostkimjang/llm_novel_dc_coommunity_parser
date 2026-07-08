from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _infer_shard_count(repo: Path) -> int:
    raw = os.getenv("MCP_SHARD_COUNT", "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except Exception:
            pass
    compose = repo / "docker-compose.warp-shards.generated.yml"
    if compose.exists():
        text = compose.read_text(encoding="utf-8", errors="ignore")
        indices = [int(m.group(1)) for m in re.finditer(r"^\s*mcp-bridge-(\d+):\s*$", text, re.MULTILINE)]
        if indices:
            return max(indices)
    return 1


def _probe(url: str, timeout: float) -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        request = Request(url, headers={"User-Agent": "llm-batch-shard-audit/1.0"})
        with urlopen(request, timeout=timeout) as response:
            body = response.read(4096)
            payload: Any = None
            content_type = response.headers.get("content-type", "")
            if "json" in content_type:
                try:
                    payload = json.loads(body.decode("utf-8", errors="ignore"))
                except Exception:
                    payload = None
            return {
                "ok": True,
                "status_code": response.status,
                "latency_ms": round((time.perf_counter() - started) * 1000.0, 1),
                "payload": payload,
                "preview": body[:200].decode("utf-8", errors="ignore"),
            }
    except HTTPError as exc:
        return {
            "ok": False,
            "status_code": exc.code,
            "latency_ms": round((time.perf_counter() - started) * 1000.0, 1),
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "latency_ms": round((time.perf_counter() - started) * 1000.0, 1),
            "error": repr(exc),
        }


def _post_json_probe(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={
                "User-Agent": "llm-batch-shard-audit/1.0",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(65536)
            parsed: Any = None
            try:
                parsed = json.loads(raw.decode("utf-8", errors="ignore"))
            except Exception:
                parsed = None
            return {
                "ok": True,
                "status_code": response.status,
                "latency_ms": round((time.perf_counter() - started) * 1000.0, 1),
                "payload": parsed,
                "preview": raw[:400].decode("utf-8", errors="ignore"),
            }
    except HTTPError as exc:
        return {
            "ok": False,
            "status_code": exc.code,
            "latency_ms": round((time.perf_counter() - started) * 1000.0, 1),
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "latency_ms": round((time.perf_counter() - started) * 1000.0, 1),
            "error": repr(exc),
        }


def _docker_state(name: str) -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            ["docker", "inspect", name, "--format", "{{json .State}}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            return {"ok": False, "error": (proc.stderr or proc.stdout).strip()}
        state = json.loads(proc.stdout.strip() or "{}")
        return {"ok": True, "state": state}
    except Exception as exc:
        return {"ok": False, "error": repr(exc)}


def _split_csv(raw: str) -> List[str]:
    return [part.strip().lower() for part in (raw or "").split(",") if part.strip()]


def _search_result_count(payload: Dict[str, Any]) -> int:
    results = payload.get("results")
    if isinstance(results, list):
        return len(results)
    try:
        return max(0, int(payload.get("total") or 0))
    except Exception:
        return 0


def _engine_names(payload: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for item in _split_csv(str(payload.get("engines") or "")):
        if item not in names:
            names.append(item)
    for item in payload.get("unresponsive_engines") or []:
        if isinstance(item, list) and item:
            name = str(item[0]).strip().lower()
        else:
            name = str(item).strip().lower()
        if name and name not in names:
            names.append(name)
    return names


def _classify_search_probe(
    probe: Dict[str, Any],
    *,
    min_results: int,
    forbidden_engines: List[str],
) -> Dict[str, Any]:
    payload = probe.get("payload") if isinstance(probe.get("payload"), dict) else {}
    reasons: List[str] = []
    if not probe.get("ok"):
        reasons.append("search_probe_http_failed")
    result_count = _search_result_count(payload)
    degraded = bool(payload.get("degraded") or payload.get("possible_throttle"))
    if degraded:
        reasons.append("search_probe_degraded")
    if result_count < min_results:
        reasons.append("search_probe_too_few_results")
    engines = _engine_names(payload)
    forbidden = sorted({engine for engine in engines if engine in set(forbidden_engines)})
    if forbidden:
        reasons.append("search_probe_forbidden_engine")
    return {
        "ok": not reasons,
        "reasons": reasons,
        "result_count": result_count,
        "raw_total": payload.get("raw_total"),
        "degraded": degraded,
        "engines": engines,
        "forbidden_engines_present": forbidden,
        "unresponsive_engines": payload.get("unresponsive_engines") or [],
        "engine_errors": payload.get("engine_errors") or payload.get("errors") or [],
    }


def build_audit(
    count: int,
    *,
    mcp_base_port: int,
    search_ui_base_port: int,
    timeout: float,
    probe_query: str = "",
    probe_purpose: str = "shard_audit",
    probe_num_results: int = 5,
    probe_min_results: int = 1,
    probe_timeout: float = 20.0,
    forbidden_engines: List[str] | None = None,
) -> Dict[str, Any]:
    shards: List[Dict[str, Any]] = []
    forbidden_engines = forbidden_engines or []
    for idx in range(1, count + 1):
        mcp_port = mcp_base_port + idx - 1
        ui_port = search_ui_base_port + idx - 1 if search_ui_base_port > 0 else 0
        healthz = _probe(f"http://127.0.0.1:{mcp_port}/healthz", timeout)
        readyz = _probe(f"http://127.0.0.1:{mcp_port}/readyz", timeout)
        ui = _probe(f"http://127.0.0.1:{ui_port}/", timeout) if ui_port > 0 else {"ok": None}
        ready_payload = readyz.get("payload") if isinstance(readyz.get("payload"), dict) else {}
        searxng_ready = bool(ready_payload.get("searxng")) if ready_payload else False
        shard_ok = bool(healthz.get("ok")) and bool(readyz.get("ok")) and searxng_ready
        if ui_port > 0:
            shard_ok = shard_ok and bool(ui.get("ok"))
        search_probe: Dict[str, Any] | None = None
        if probe_query.strip():
            probe_raw = _post_json_probe(
                f"http://127.0.0.1:{mcp_port}/mcp/search",
                {
                    "query": probe_query.strip(),
                    "num_results": max(1, probe_num_results),
                    "purpose": probe_purpose or "shard_audit",
                },
                probe_timeout,
            )
            probe_classification = _classify_search_probe(
                probe_raw,
                min_results=max(0, probe_min_results),
                forbidden_engines=forbidden_engines,
            )
            search_probe = {
                "query": probe_query.strip(),
                "purpose": probe_purpose or "shard_audit",
                "num_results": max(1, probe_num_results),
                **probe_classification,
                "http": {
                    key: probe_raw.get(key)
                    for key in ("ok", "status_code", "latency_ms", "error")
                    if key in probe_raw
                },
            }
            shard_ok = shard_ok and bool(search_probe.get("ok"))
        shards.append(
            {
                "shard": idx,
                "mcp_port": mcp_port,
                "search_ui_port": ui_port,
                "ok": shard_ok,
                "healthz": healthz,
                "readyz": readyz,
                "search_probe": search_probe,
                "search_ui": ui,
                "docker": {
                    "warp": _docker_state(f"warp-shards-warp-{idx}-1"),
                    "searchxng": _docker_state(f"warp-shards-searchxng-{idx}-1"),
                    "mcp_bridge": _docker_state(f"warp-shards-mcp-bridge-{idx}-1"),
                    "browser_search": _docker_state(f"warp-shards-browser-search-{idx}-1"),
                },
            }
        )
    bad = [item for item in shards if not item.get("ok")]
    probe_items = [item.get("search_probe") for item in shards if isinstance(item.get("search_probe"), dict)]
    probe_bad = [
        item["shard"]
        for item in shards
        if isinstance(item.get("search_probe"), dict) and not item["search_probe"].get("ok")
    ]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "count": count,
        "ok_count": count - len(bad),
        "bad_count": len(bad),
        "bad_shards": [item["shard"] for item in bad],
        "search_probe_summary": {
            "enabled": bool(probe_items),
            "query": probe_query.strip(),
            "ok_count": len(probe_items) - len(probe_bad),
            "bad_count": len(probe_bad),
            "bad_shards": probe_bad,
            "degraded_count": sum(1 for item in probe_items if item.get("degraded")),
            "forbidden_engine_count": sum(1 for item in probe_items if item.get("forbidden_engines_present")),
        },
        "shards": shards,
    }


def main() -> None:
    repo = _repo_root()
    parser = argparse.ArgumentParser(description="Audit local MCP/SearchXNG/browser-search shard readiness.")
    parser.add_argument("--count", type=int, default=_infer_shard_count(repo))
    parser.add_argument("--mcp-base-port", type=int, default=int(os.getenv("MCP_SHARD_BASE_PORT", "3333")))
    parser.add_argument(
        "--search-ui-base-port",
        type=int,
        default=int(os.getenv("WARP_SHARDS_SEARCH_UI_BASE_PORT", "19001")),
    )
    parser.add_argument("--timeout", type=float, default=2.5)
    parser.add_argument("--probe-query", default="")
    parser.add_argument("--probe-purpose", default="shard_audit")
    parser.add_argument("--probe-num-results", type=int, default=5)
    parser.add_argument("--probe-min-results", type=int, default=1)
    parser.add_argument("--probe-timeout", type=float, default=20.0)
    parser.add_argument(
        "--forbidden-engines",
        default="presearch,yahoo,yahoo_news,wikidata,wikipedia",
        help="Comma-separated engines that make query-level shard readiness fail when observed.",
    )
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    audit = build_audit(
        max(1, args.count),
        mcp_base_port=args.mcp_base_port,
        search_ui_base_port=args.search_ui_base_port,
        timeout=max(0.5, args.timeout),
        probe_query=args.probe_query,
        probe_purpose=args.probe_purpose,
        probe_num_results=max(1, args.probe_num_results),
        probe_min_results=max(0, args.probe_min_results),
        probe_timeout=max(1.0, args.probe_timeout),
        forbidden_engines=_split_csv(args.forbidden_engines),
    )
    output = Path(args.output) if args.output else repo / "out" / f"search_shard_audit_{datetime.now():%Y%m%d_%H%M%S}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"WROTE {output}")
    print(f"ok={audit['ok_count']}/{audit['count']} bad={audit['bad_shards']}")
    probe = audit.get("search_probe_summary") or {}
    if probe.get("enabled"):
        print(
            "query_probe ok={ok}/{count} bad={bad} degraded={degraded} forbidden_engine={forbidden}".format(
                ok=probe.get("ok_count"),
                count=audit["count"],
                bad=probe.get("bad_shards"),
                degraded=probe.get("degraded_count"),
                forbidden=probe.get("forbidden_engine_count"),
            )
        )


if __name__ == "__main__":
    main()
