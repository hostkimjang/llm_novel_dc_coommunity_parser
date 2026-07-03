from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PLATFORM_HOSTS = (
    "novelpia.com",
    "munpia.com",
    "series.naver.com",
    "page.kakao.com",
    "joara.com",
    "ridibooks.com",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _parse_endpoints(raw: str) -> List[str]:
    endpoints: List[str] = []
    for part in str(raw or "").split(","):
        endpoint = part.strip().rstrip("/")
        if endpoint and endpoint not in endpoints:
            endpoints.append(endpoint)
    return endpoints or ["http://127.0.0.1:3333"]


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                yield row


def _latest_review_packet(repo: Path, run_id: str) -> Path:
    out_dir = repo / "out" / "llm_judgment_reviews"
    pattern = f"llm_judgment_review_{run_id}_*.jsonl"
    candidates = sorted(out_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No review packet found for run id: {run_id}")
    return candidates[0]


def _queries_from_item(item: Dict[str, Any], max_queries: int) -> List[str]:
    exp = item.get("query_experiment") if isinstance(item.get("query_experiment"), dict) else {}
    queries = exp.get("query_variants") if isinstance(exp.get("query_variants"), list) else []
    out: List[str] = []
    seen: set[str] = set()
    for query in queries:
        text = str(query or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= max_queries:
            break
    return out


def _platform_hits(results: List[Dict[str, Any]]) -> int:
    count = 0
    for item in results:
        url = str(item.get("url") or "").lower()
        if any(host in url for host in PLATFORM_HOSTS):
            count += 1
    return count


def _platform_detail_hits(results: List[Dict[str, Any]]) -> int:
    count = 0
    for item in results:
        url = str(item.get("url") or "").lower()
        if (
            "novelpia.com/novel/" in url
            or "novel.munpia.com/" in url
            or "munpia.com/novel/detail" in url
            or "series.naver.com/novel/detail.series" in url
            or "page.kakao.com/content/" in url
            or "joara.com/book/" in url
            or "ridibooks.com/books/" in url
        ):
            count += 1
    return count


def _probe(endpoint: str, query: str, *, num_results: int, timeout: float) -> Dict[str, Any]:
    started = time.perf_counter()
    payload = json.dumps(
        {"query": query, "num_results": num_results, "purpose": "query_expansion_probe"},
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        f"{endpoint.rstrip('/')}/mcp/search",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "query-expansion-probe/1.0"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(2_000_000)
            data = json.loads(raw.decode("utf-8", errors="ignore") or "{}")
            if not isinstance(data, dict):
                data = {}
            results = data.get("results") if isinstance(data.get("results"), list) else []
            return {
                "ok": True,
                "query": query,
                "endpoint": endpoint,
                "latency_ms": round((time.perf_counter() - started) * 1000.0, 1),
                "total": data.get("total"),
                "result_count": len(results),
                "platform_hit_count": _platform_hits(results),
                "platform_detail_hit_count": _platform_detail_hits(results),
                "degraded": bool(data.get("degraded")),
                "possible_throttle": bool(data.get("possible_throttle")),
                "top_results": [
                    {"title": r.get("title"), "url": r.get("url")}
                    for r in results[:3]
                    if isinstance(r, dict)
                ],
            }
    except HTTPError as exc:
        return {
            "ok": False,
            "query": query,
            "endpoint": endpoint,
            "latency_ms": round((time.perf_counter() - started) * 1000.0, 1),
            "error": f"HTTP {exc.code}: {exc.reason}",
        }
    except (TimeoutError, URLError, Exception) as exc:
        return {
            "ok": False,
            "query": query,
            "endpoint": endpoint,
            "latency_ms": round((time.perf_counter() - started) * 1000.0, 1),
            "error": repr(exc),
        }


def _write_markdown(path: Path, report: Dict[str, Any]) -> None:
    lines = [
        f"# Search Query Expansion Probe - {report.get('run_id') or 'manual'}",
        "",
        f"- generated_at: {report.get('generated_at')}",
        f"- source_packet: {report.get('source_packet')}",
        f"- item_count: {report.get('item_count')}",
        f"- query_count: {report.get('query_count')}",
        f"- ok_queries: {report.get('ok_queries')}",
        f"- timeout_or_error_queries: {report.get('error_queries')}",
        "",
        "## Summary",
        "",
        f"- base_queries_with_platform_hit: {report.get('base_queries_with_platform_hit')}",
        f"- expanded_queries_with_platform_hit: {report.get('expanded_queries_with_platform_hit')}",
        f"- base_queries_with_platform_detail_hit: {report.get('base_queries_with_platform_detail_hit')}",
        f"- expanded_queries_with_platform_detail_hit: {report.get('expanded_queries_with_platform_detail_hit')}",
        f"- note: {report.get('note')}",
        "",
    ]
    for item in report.get("items") or []:
        lines.extend(
            [
                f"## post_id={item.get('post_id')} bucket={item.get('sample_bucket')}",
                "",
                f"- title: {item.get('title')}",
                "",
            ]
        )
        for result in item.get("queries") or []:
            lines.append(
                "- `{}` ok={} results={} platform_hits={} detail_hits={} degraded={} latency_ms={}".format(
                    result.get("query"),
                    result.get("ok"),
                    result.get("result_count"),
                    result.get("platform_hit_count"),
                    result.get("platform_detail_hit_count"),
                    result.get("degraded"),
                    result.get("latency_ms"),
                )
            )
            if result.get("error"):
                lines.append(f"  - error: `{result.get('error')}`")
            for top in result.get("top_results") or []:
                lines.append(f"  - {top.get('title')} | {top.get('url')}")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    repo = _repo_root()
    parser = argparse.ArgumentParser(description="Probe whether expanded novel search queries improve platform hits.")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--input-jsonl", default="")
    parser.add_argument("--limit-items", type=int, default=10)
    parser.add_argument("--max-queries-per-item", type=int, default=6)
    parser.add_argument("--manual-query", action="append", default=[])
    parser.add_argument("--endpoint", default=os.getenv("MCP_ENDPOINT", "http://127.0.0.1:3333"))
    parser.add_argument("--num-results", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    args = parser.parse_args()

    endpoints = _parse_endpoints(args.endpoint)
    items: List[Dict[str, Any]] = []
    source_packet = ""
    if args.manual_query:
        items = [
            {
                "post_id": "manual",
                "sample_bucket": "manual",
                "title": "manual query probe",
                "query_experiment": {"query_variants": args.manual_query},
            }
        ]
    else:
        if args.input_jsonl:
            input_jsonl = Path(args.input_jsonl)
        elif args.run_id:
            input_jsonl = _latest_review_packet(repo, args.run_id)
        else:
            raise SystemExit("--run-id, --input-jsonl, or --manual-query is required")
        source_packet = str(input_jsonl)
        for row in _iter_jsonl(input_jsonl):
            if _queries_from_item(row, args.max_queries_per_item):
                items.append(row)
            if len(items) >= max(1, args.limit_items):
                break

    report_items: List[Dict[str, Any]] = []
    query_count = 0
    ok_queries = 0
    error_queries = 0
    base_platform_hit = 0
    expanded_platform_hit = 0
    base_platform_detail_hit = 0
    expanded_platform_detail_hit = 0
    endpoint_idx = 0
    for item in items:
        query_results: List[Dict[str, Any]] = []
        queries = _queries_from_item(item, max(1, args.max_queries_per_item))
        base_query = queries[0] if queries else ""
        for query in queries:
            endpoint = endpoints[endpoint_idx % len(endpoints)]
            endpoint_idx += 1
            result = _probe(endpoint, query, num_results=max(1, args.num_results), timeout=max(1.0, args.timeout))
            query_count += 1
            ok_queries += 1 if result.get("ok") else 0
            error_queries += 0 if result.get("ok") else 1
            if int(result.get("platform_hit_count") or 0) > 0:
                if query == base_query:
                    base_platform_hit += 1
                else:
                    expanded_platform_hit += 1
            if int(result.get("platform_detail_hit_count") or 0) > 0:
                if query == base_query:
                    base_platform_detail_hit += 1
                else:
                    expanded_platform_detail_hit += 1
            query_results.append(result)
        report_items.append(
            {
                "post_id": item.get("post_id"),
                "sample_bucket": item.get("sample_bucket"),
                "risk_tags": item.get("risk_tags"),
                "title": item.get("title"),
                "queries": query_results,
            }
        )

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_id": args.run_id,
        "source_packet": source_packet,
        "item_count": len(report_items),
        "query_count": query_count,
        "ok_queries": ok_queries,
        "error_queries": error_queries,
        "base_queries_with_platform_hit": base_platform_hit,
        "expanded_queries_with_platform_hit": expanded_platform_hit,
        "base_queries_with_platform_detail_hit": base_platform_detail_hit,
        "expanded_queries_with_platform_detail_hit": expanded_platform_detail_hit,
        "note": "소량 프로브입니다. 쿼리 확장 효과는 같은 post id 재처리와 false positive 리뷰로 확인해야 합니다.",
        "items": report_items,
    }

    out_dir = repo / "out" / "search_query_experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_json = Path(args.output_json) if args.output_json else out_dir / f"search_query_expansion_{stamp}.json"
    output_md = Path(args.output_md) if args.output_md else out_dir / f"search_query_expansion_{stamp}.md"
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(output_md, report)
    print(f"WROTE {output_json}")
    print(f"WROTE {output_md}")
    print(
        "queries={} ok={} errors={} base_platform_hits={} expanded_platform_hits={} base_detail_hits={} expanded_detail_hits={}".format(
            query_count,
            ok_queries,
            error_queries,
            base_platform_hit,
            expanded_platform_hit,
            base_platform_detail_hit,
            expanded_platform_detail_hit,
        )
    )


if __name__ == "__main__":
    main()
