from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


REGISTRY_SOURCES = {
    "KNOWN_ABBREVIATIONS": Path("src/llm_batch/experts/decoder.py"),
    "KNOWN_TITLE_ABBREVIATIONS": Path("src/llm_batch/experts/utils.py"),
    "SLANG_DICTIONARY": Path("src/llm_batch/rules.py"),
}

REGISTRY_MARKERS = {
    "known_abbr",
    "known_abbreviation",
    "known_title_abbreviation",
    "KNOWN_ABBREVIATIONS",
    "KNOWN_TITLE_ABBREVIATIONS",
    "SLANG_DICTIONARY",
}

REPORT_NAME_MARKERS = (
    "hardcoded_alias",
    "goal_action_queue",
    "semantic_coverage",
    "current_state_map",
    "process_snapshot",
    "reason_hygiene",
    "preflight",
    "manifest",
)

TEXT_FIELD_HINTS = {
    "title",
    "content",
    "body",
    "text",
    "comment",
    "comments",
    "reason",
    "notes",
    "snippet",
    "evidence",
    "analysis",
    "analysis_result",
    "identity",
    "slang_insight",
    "title_candidates",
    "primary_work",
    "primary_subject_text",
    "entity_mentions",
}


@dataclass(frozen=True)
class AliasEntry:
    registry: str
    alias: str
    canonical: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def normalize_surface(value: Any) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", str(value or "")).lower()


def short_text(value: Any, limit: int = 500) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _stringify_canonical(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)) and value:
        return str(value[0])
    return str(value)


def _literal_assignment(tree: ast.AST, name: str) -> Any | None:
    for node in ast.walk(tree):
        value: ast.AST | None = None
        targets: list[ast.AST] = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = [node.target]
        if value is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                try:
                    return ast.literal_eval(value)
                except (SyntaxError, ValueError):
                    return None
    return None


def load_registry_entries(root: Path) -> list[AliasEntry]:
    entries: list[AliasEntry] = []
    for registry, rel_path in REGISTRY_SOURCES.items():
        path = root / rel_path
        if not path.exists():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(rel_path))
        except SyntaxError:
            continue
        payload = _literal_assignment(tree, registry)
        if not isinstance(payload, dict):
            continue
        for alias, canonical in payload.items():
            if not isinstance(alias, str):
                continue
            alias_clean = alias.strip()
            canonical_text = _stringify_canonical(canonical).strip()
            if not alias_clean or not canonical_text:
                continue
            entries.append(AliasEntry(registry=registry, alias=alias_clean, canonical=canonical_text))
    return entries


def _load_json_or_jsonl(path: Path) -> list[Any]:
    text = path.read_text(encoding="utf-8-sig")
    stripped = text.lstrip()
    if not stripped:
        return []
    if stripped[0] in "[{":
        try:
            return [json.loads(text)]
        except json.JSONDecodeError:
            # Some historical result artifacts use a .json extension while storing JSONL.
            pass
    records: list[Any] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSONL: {exc}") from exc
        records.append(item)
    return records


def _records_from_payload(payload: Any) -> list[tuple[int, Any]]:
    if isinstance(payload, list):
        return list(enumerate(payload))
    if isinstance(payload, dict):
        for key in (
            "review_packets",
            "packets",
            "labels",
            "records",
            "results",
            "items",
            "actions",
        ):
            value = payload.get(key)
            if isinstance(value, list):
                return list(enumerate(value))
        return [(0, payload)]
    return [(0, payload)]


def _iter_leaf_strings(value: Any, prefix: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield prefix, value
        return
    if isinstance(value, (int, float, bool)) or value is None:
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _iter_leaf_strings(item, f"{prefix}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _iter_leaf_strings(item, f"{prefix}.{key}")


def _is_informative_string_path(path: str) -> bool:
    lower = path.lower()
    return any(hint in lower for hint in TEXT_FIELD_HINTS)


def _field_category(path: str) -> str:
    lower = path.lower()
    if any(
        marker in lower
        for marker in (
            "search_evidence",
            "evidence_catalog",
            ".snippet",
            ".url",
            ".domain",
            ".query",
            ".source_tier",
        )
    ):
        return "evidence_context"
    if lower in {"$.title", "$.content", "$.body", "$.text"} or any(
        marker in lower
        for marker in (
            "$.comments",
            "$.packet.title",
            "$.packet.body",
            "$.packet.content",
            "$.packet.comments",
        )
    ):
        return "post_context"
    if any(
        marker in lower
        for marker in (
            "slang_insight",
            "title_candidates",
            "primary_work",
            "novel_identity",
            "detected_titles",
            "entity_mentions",
            "resolved_title",
            "official_title",
            "reason",
            "notes",
            "primary_subject_text",
        )
    ):
        return "decision_context"
    return "other_text"


def _text_index(record: Any) -> list[tuple[str, str, str, str]]:
    strings: list[tuple[str, str, str, str]] = []
    for path, text in _iter_leaf_strings(record):
        if not text.strip():
            continue
        if _is_informative_string_path(path):
            strings.append((path, text, normalize_surface(text), _field_category(path)))
    return strings


def _get_path(value: Any, *paths: tuple[str, ...]) -> Any:
    for path in paths:
        current = value
        ok = True
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                ok = False
                break
        if ok and current not in (None, "", []):
            return current
    return None


def _comment_excerpt(record: Any) -> str:
    comments = _get_path(record, ("comments",), ("comment_excerpts",), ("comments_excerpt",))
    if isinstance(comments, list):
        chunks: list[str] = []
        for item in comments[:3]:
            if isinstance(item, dict):
                author = item.get("author") or item.get("comment_author") or ""
                text = item.get("content") or item.get("text") or item.get("body") or ""
                chunks.append(short_text(f"{author}: {text}", 180))
            else:
                chunks.append(short_text(item, 180))
        return " / ".join(chunk for chunk in chunks if chunk)
    return short_text(comments, 400)


def _resolved_title(record: Any) -> Any:
    return _get_path(
        record,
        ("resolved_title",),
        ("official_title",),
        ("analysis_result", "identity", "novel_identity", "official_title"),
        ("analysis_result", "identity", "primary_work", "official_title"),
        ("analysis_result", "analysis", "detected_titles", 0, "official_title"),
    )


def _get_with_numeric_path(value: Any, path: tuple[Any, ...]) -> Any:
    current = value
    for key in path:
        if isinstance(key, int):
            if isinstance(current, list) and len(current) > key:
                current = current[key]
            else:
                return None
        elif isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def _nested(record: Any, *paths: tuple[Any, ...]) -> Any:
    for path in paths:
        current = _get_with_numeric_path(record, path)
        if current not in (None, "", []):
            return current
    return None


def _packet_metadata(record: Any, source_path: str, row_index: int) -> dict[str, Any]:
    identity = _nested(record, ("analysis_result", "identity")) or {}
    analysis = _nested(record, ("analysis_result", "analysis")) or {}
    return {
        "packet_id": f"{source_path}#{row_index}",
        "source_path": source_path,
        "row_index": row_index,
        "post_id": _nested(record, ("post_id",), ("analysis_result", "post_id"), ("packet", "post_id")),
        "title": short_text(_nested(record, ("title",), ("post_title",), ("packet", "title")), 300),
        "body_excerpt": short_text(_nested(record, ("content",), ("body",), ("text",), ("packet", "body")), 700),
        "comment_excerpt": _comment_excerpt(record),
        "resolved_title": short_text(
            _nested(
                record,
                ("resolved_title",),
                ("official_title",),
                ("analysis_result", "identity", "novel_identity", "official_title"),
                ("analysis_result", "identity", "primary_work", "official_title"),
                ("analysis_result", "analysis", "detected_titles", 0, "official_title"),
            ),
            300,
        ),
        "relevance": _nested(
            record,
            ("relevance",),
            ("is_relevant",),
            ("analysis_result", "identity", "is_relevant"),
        ),
        "discussion_type": identity.get("discussion_type") if isinstance(identity, dict) else None,
        "primary_subject_type": identity.get("primary_subject_type") if isinstance(identity, dict) else None,
        "reason": short_text(
            _nested(record, ("reason",), ("analysis_result", "identity", "reason"), ("label_reason",)),
            900,
        ),
        "analysis_notes": short_text(analysis.get("notes") if isinstance(analysis, dict) else None, 600),
    }


def _marker_hits(strings: list[tuple[str, str, str, str]]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for path, text, _normalized, category in strings:
        for marker in REGISTRY_MARKERS:
            if marker in text:
                hits.append(
                    {
                        "marker": marker,
                        "path": path,
                        "category": category,
                        "excerpt": short_text(text, 240),
                    }
                )
    return hits


def _alias_hits(
    strings: list[tuple[str, str, str, str]],
    entries: list[AliasEntry],
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for entry in entries:
        alias_norm = normalize_surface(entry.alias)
        if len(alias_norm) < 2:
            continue
        locations: list[dict[str, str]] = []
        category_counts: Counter[str] = Counter()
        for path, text, normalized, category in strings:
            if alias_norm in normalized:
                category_counts[category] += 1
                locations.append(
                    {"path": path, "category": category, "excerpt": short_text(text, 240)}
                )
        if locations:
            has_post_context = bool(category_counts.get("post_context"))
            has_decision_context = bool(category_counts.get("decision_context"))
            has_evidence_context = bool(category_counts.get("evidence_context"))
            if has_post_context:
                match_surface_scope = "post_context"
            elif has_decision_context:
                match_surface_scope = "decision_context"
            elif has_evidence_context:
                match_surface_scope = "evidence_context"
            else:
                match_surface_scope = "other_text"
            hits.append(
                {
                    "registry": entry.registry,
                    "alias": entry.alias,
                    "canonical": entry.canonical,
                    "qualifies_for_packet_match": any(
                        category in {"post_context", "decision_context"}
                        for category in category_counts
                    ),
                    "has_post_context": has_post_context,
                    "has_decision_context": has_decision_context,
                    "has_evidence_context": has_evidence_context,
                    "match_surface_scope": match_surface_scope,
                    "category_counts": dict(sorted(category_counts.items())),
                    "match_locations": locations[:8],
                }
            )
    return hits


def should_skip_scan_file(path: Path) -> bool:
    stem = path.stem.lower()
    return any(marker in stem for marker in REPORT_NAME_MARKERS)


def scan_files(root: Path, paths: Iterable[Path], entries: list[AliasEntry]) -> dict[str, Any]:
    files = sorted(dict.fromkeys(path.resolve() for path in paths if path.exists() and path.is_file()))
    scanned_files = 0
    skipped_files: list[str] = []
    records_scanned = 0
    matched_packets: list[dict[str, Any]] = []
    registry_counts: Counter[str] = Counter()
    post_context_registry_counts: Counter[str] = Counter()
    decision_context_registry_counts: Counter[str] = Counter()
    context_only_registry_counts: Counter[str] = Counter()
    marker_counter: Counter[str] = Counter()
    unique_registry_matches: set[tuple[str, str, str, str, str]] = set()
    unique_post_context_registry_matches: set[tuple[str, str, str, str]] = set()
    unique_decision_context_registry_matches: set[tuple[str, str, str, str]] = set()
    unique_context_only_registry_matches: set[tuple[str, str, str, str, str]] = set()

    for path in files:
        source_path = display_path(path, root)
        if should_skip_scan_file(path):
            skipped_files.append(source_path)
            continue
        scanned_files += 1
        for payload in _load_json_or_jsonl(path):
            for row_index, record in _records_from_payload(payload):
                records_scanned += 1
                strings = _text_index(record)
                markers = _marker_hits(strings)
                aliases = _alias_hits(strings, entries)
                qualifying_aliases = [
                    hit for hit in aliases if hit.get("qualifies_for_packet_match")
                ]
                context_only_aliases = [
                    hit for hit in aliases if not hit.get("qualifies_for_packet_match")
                ]
                if not markers and not qualifying_aliases:
                    continue
                packet = _packet_metadata(record, source_path, row_index)
                post_key = str(packet.get("post_id") or packet.get("packet_id") or "")
                for hit in qualifying_aliases:
                    registry_counts[str(hit["registry"])] += 1
                    unique_registry_matches.add(
                        (
                            post_key,
                            str(hit["registry"]),
                            str(hit["alias"]),
                            str(hit["canonical"]),
                            str(hit.get("match_surface_scope") or ""),
                        )
                    )
                    if hit.get("has_post_context"):
                        post_context_registry_counts[str(hit["registry"])] += 1
                        unique_post_context_registry_matches.add(
                            (
                                post_key,
                                str(hit["registry"]),
                                str(hit["alias"]),
                                str(hit["canonical"]),
                            )
                        )
                    elif hit.get("has_decision_context"):
                        decision_context_registry_counts[str(hit["registry"])] += 1
                        unique_decision_context_registry_matches.add(
                            (
                                post_key,
                                str(hit["registry"]),
                                str(hit["alias"]),
                                str(hit["canonical"]),
                            )
                        )
                for hit in context_only_aliases:
                    context_only_registry_counts[str(hit["registry"])] += 1
                    unique_context_only_registry_matches.add(
                        (
                            post_key,
                            str(hit["registry"]),
                            str(hit["alias"]),
                            str(hit["canonical"]),
                            str(hit.get("match_surface_scope") or ""),
                        )
                    )
                for hit in markers:
                    marker_counter[str(hit["marker"])] += 1
                packet.update(
                    {
                        "marker_hits": markers,
                        "alias_matches": qualifying_aliases,
                        "context_only_alias_matches": context_only_aliases,
                        "review_label": "HOLD",
                        "action": "human_review",
                        "review_note": (
                            "hardcoded positive alias registry 또는 관련 marker가 packet에 나타났으므로 "
                            "원문/evidence/reason을 사람이 확인하기 전에는 semantic approval 근거로 쓰지 않는다."
                        ),
                    }
                )
                matched_packets.append(packet)

    packet_coverage = "FOUND" if matched_packets else "MISSING"
    gate = "REVIEW" if matched_packets else "INFO_MISSING"
    return {
        "review_type": "hardcoded_alias_packet_review",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "registry_sources": {name: path.as_posix() for name, path in REGISTRY_SOURCES.items()},
        "summary": {
            "scanned_files": scanned_files,
            "skipped_report_files": len(skipped_files),
            "scanned_records": records_scanned,
            "registry_entry_count": len(entries),
            "matched_packets": len(matched_packets),
            "unique_registry_match_count": len(unique_registry_matches),
            "unique_post_context_registry_match_count": len(unique_post_context_registry_matches),
            "unique_decision_context_only_registry_match_count": len(
                unique_decision_context_registry_matches
            ),
            "unique_context_only_registry_match_count": len(unique_context_only_registry_matches),
            "packet_coverage": packet_coverage,
            "gate": gate,
            "semantic_approval": "not_granted_by_packet_review",
            "registry_match_counts": dict(sorted(registry_counts.items())),
            "post_context_registry_match_counts": dict(sorted(post_context_registry_counts.items())),
            "decision_context_only_registry_match_counts": dict(sorted(decision_context_registry_counts.items())),
            "context_only_registry_match_counts": dict(sorted(context_only_registry_counts.items())),
            "marker_hit_counts": dict(sorted(marker_counter.items())),
        },
        "skipped_files": skipped_files[:200],
        "packets": matched_packets,
        "next_actions": _next_actions(packet_coverage),
    }


def _next_actions(packet_coverage: str) -> list[dict[str, str]]:
    if packet_coverage == "FOUND":
        return [
            {
                "priority": "P1",
                "action": "packet_human_review",
                "detail": "matched packet별 원문/evidence/reason을 ACCEPT/HOLD/REPROCESS/REJECT로 재라벨링한다.",
            },
            {
                "priority": "P1",
                "action": "remove_or_guard_positive_registry_path",
                "detail": "직접 positive 해소 registry가 evidence gate 없이 확정되는 코드 경로를 축소하거나 guard한다.",
            },
        ]
    return [
        {
            "priority": "P1",
            "action": "targeted_canary_required",
            "detail": "현재 산출물에는 hardcoded alias registry 영향을 받은 packet 근거가 부족하므로 각 registry alias별 targeted canary를 만든다.",
        },
        {
            "priority": "P2",
            "action": "increase_packet_coverage",
            "detail": "완료 source에서 alias registry marker/source hit이 노출되는 packet 필드를 보존하도록 review packet builder를 보강한다.",
        },
    ]


def write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    lines = [
        "# Hardcoded Alias Packet 리뷰",
        "",
        "## 요약",
        f"- gate: `{summary.get('gate')}`",
        f"- semantic approval: `{summary.get('semantic_approval')}`",
        f"- packet coverage: `{summary.get('packet_coverage')}`",
        f"- scanned files: {summary.get('scanned_files', 0)}",
        f"- scanned records: {summary.get('scanned_records', 0)}",
        f"- registry entries: {summary.get('registry_entry_count', 0)}",
        f"- matched packets: {summary.get('matched_packets', 0)}",
        f"- unique registry matches: `{summary.get('unique_registry_match_count', 0)}`",
        (
            "- unique post-context registry matches: "
            f"`{summary.get('unique_post_context_registry_match_count', 0)}`"
        ),
        (
            "- unique decision-context-only registry matches: "
            f"`{summary.get('unique_decision_context_only_registry_match_count', 0)}`"
        ),
        f"- skipped report files: {summary.get('skipped_report_files', 0)}",
        "",
        "## Registry/Marker 분포",
        f"- registry match counts: `{summary.get('registry_match_counts') or {}}`",
        f"- post-context registry match counts: `{summary.get('post_context_registry_match_counts') or {}}`",
        f"- decision-context-only registry match counts: `{summary.get('decision_context_only_registry_match_counts') or {}}`",
        f"- context-only registry match counts: `{summary.get('context_only_registry_match_counts') or {}}`",
        f"- marker hit counts: `{summary.get('marker_hit_counts') or {}}`",
        "",
    ]
    packets = payload.get("packets") or []
    if packets:
        lines.extend(
            [
                "## Packet 샘플",
                "| packet | post_id | title | resolved_title | label/action | match |",
                "|---|---:|---|---|---|---|",
            ]
        )
        for packet in packets[:30]:
            match_summary = []
            for hit in packet.get("alias_matches") or []:
                match_summary.append(
                    f"{hit.get('registry')}:{hit.get('alias')}->{hit.get('canonical')}"
                )
            for hit in packet.get("marker_hits") or []:
                match_summary.append(f"marker:{hit.get('marker')}")
            lines.append(
                "| `{packet}` | {post_id} | {title} | {resolved} | {label}/{action} | {match} |".format(
                    packet=packet.get("packet_id", ""),
                    post_id=packet.get("post_id", ""),
                    title=short_text(packet.get("title"), 80).replace("|", "\\|"),
                    resolved=short_text(packet.get("resolved_title"), 80).replace("|", "\\|"),
                    label=packet.get("review_label", ""),
                    action=packet.get("action", ""),
                    match=short_text("; ".join(match_summary), 140).replace("|", "\\|"),
                )
            )
        lines.append("")
    else:
        lines.extend(
            [
                "## Packet 근거 상태",
                "- 현재 scan 대상에서는 hardcoded positive alias registry/marker가 실제 packet에 드러난 사례를 찾지 못했습니다.",
                "- 이는 안전하다는 뜻이 아니라, packet coverage가 부족하다는 뜻입니다.",
                "- registry별 targeted canary와 completed source packet 보존 여부 확인이 필요합니다.",
                "",
            ]
        )

    lines.extend(["## 다음 조치"])
    for item in payload.get("next_actions") or []:
        lines.append(f"- `{item.get('priority')}` `{item.get('action')}`: {item.get('detail')}")
    lines.append("")
    return "\n".join(lines)


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_markdown(payload), encoding="utf-8")


def expand_scan_paths(root: Path, result_paths: Iterable[str], scan_globs: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for raw in result_paths:
        if not raw:
            continue
        path = Path(raw)
        paths.append(path if path.is_absolute() else root / path)
    for pattern in scan_globs:
        for path in root.glob(pattern):
            paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(repo_root()))
    parser.add_argument("--result", action="append", default=[])
    parser.add_argument("--scan-glob", action="append", default=[])
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    entries = load_registry_entries(root)
    paths = expand_scan_paths(root, args.result, args.scan_glob)
    payload = scan_files(root, paths, entries)

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    if not output_json.is_absolute():
        output_json = root / output_json
    if not output_md.is_absolute():
        output_md = root / output_md
    write_json(payload, output_json)
    write_markdown(payload, output_md)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(build_markdown(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
