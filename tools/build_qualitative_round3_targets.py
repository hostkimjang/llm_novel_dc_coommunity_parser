from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict, OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


RUN_ID = "20260505_214349_324347"
ROUND_NAME = "round3_p0p1_target_selection"
SEED = f"{RUN_ID}:round3_p0p1_targets:v1"

PATTERN_DEFINITIONS = OrderedDict(
    [
        (
            "generic_common_surface",
            {
                "priority": "P0/P1",
                "buckets": {
                    "known_case_mismatch",
                    "generic_title_surface",
                    "generic_parenthetical_bridge",
                    "medical_common_regression",
                },
                "actions": {"re_judge", "docs_issue", "re_search"},
                "hypothesis": "generic/common surface가 직접 title 근거 없이 작품명으로 승격되거나 resolution을 강화하고 있다.",
                "required_evidence": "현재 코드는 final title freeze 전에 generic surface를 거부하거나, 근거 약함을 명시해 HOLD/REPROCESS로 보내야 한다.",
            },
        ),
        (
            "weak_evidence_strong_resolution",
            {
                "priority": "P1",
                "buckets": {
                    "weak_evidence_but_strong_resolution",
                    "unresolved_to_resolved",
                    "weak_evidence_resolved",
                    "low_anchor_resolved",
                    "degraded_majority_resolved",
                    "search_degraded_or_timeout",
                },
                "actions": {"re_search", "re_judge"},
                "hypothesis": "약하거나 degraded 된 근거를 가진 row가 여전히 resolved/high-confidence 판정을 받고 있다.",
                "required_evidence": "re_search/re_judge는 직접 공식/title 근거를 추가하거나 판정을 HOLD/REPROCESS로 낮춰야 한다.",
            },
        ),
        (
            "alias_recall_loss_false_negative",
            {
                "priority": "P1",
                "buckets": {
                    "relevant_without_title",
                    "round2_false_negative_recall",
                    "possible_false_negative_novel_cue",
                    "control_non_relevant",
                    "random_control",
                },
                "actions": {"re_search", "re_judge", "human_review"},
                "hypothesis": "눈에 보이는 작품/도메인 단서와 known alias가 unresolved로 남거나 non-relevant로 강등되고 있다.",
                "required_evidence": "현재 코드는 alias/work title을 회수하거나, 깔끔한 승인 대신 row를 HOLD/REPROCESS로 명시 라우팅해야 한다.",
            },
        ),
        (
            "slang_db_alias_subtype",
            {
                "priority": "P1",
                "buckets": {"slang_db_store_block_pending_family_noise", "slang_noise_candidate"},
                "actions": {"slang_db_review", "re_search"},
                "hypothesis": "slang_db alias metadata가 pure alias, family alias, noise, display-state ambiguity를 섞고 있다.",
                "required_evidence": "alias 후보는 신뢰 저장 전에 confirmed/pending/family/noise/display 상태로 분리되어야 한다.",
            },
        ),
        (
            "vlm_ocr_evidence_gap",
            {
                "priority": "P1",
                "buckets": {"VLM_OCR_involved", "slang_noise_candidate"},
                "actions": {"re_run", "re_search"},
                "hypothesis": "OCR/VLM 불확실성이 있는데 image/OCR 개입 row가 약한 공개 근거로 ACCEPT 또는 resolved 되고 있다.",
                "required_evidence": "targeted rerun은 안정적인 OCR/VLM field를 보이거나 row를 REPROCESS/HOLD로 보내야 한다.",
            },
        ),
        (
            "worker_shard_degraded_window",
            {
                "priority": "P1",
                "buckets": {"worker_or_shard_degraded_window", "search_degraded_or_timeout"},
                "actions": {"re_search"},
                "hypothesis": "검색 degradation이 worker window와 연결되지만 server-poc에는 row별 shard/timestamp lineage가 없다.",
                "required_evidence": "다음 run package에는 shard/timestamp/checkpoint lineage가 포함되어야 하며, 현재 row는 re_search 또는 HOLD가 필요하다.",
            },
        ),
        (
            "boundary_domain_drift",
            {
                "priority": "P1/P2",
                "buckets": {"multi_work_or_adjacent_risk", "trope_or_author_talk_risk", "low_anchor_resolved"},
                "actions": {"human_review", "re_judge", "re_search"},
                "hypothesis": "adjacent work, trope/meta/author talk, 비웹소설 도메인 row가 work-title resolution으로 drift 될 수 있다.",
                "required_evidence": "직접 작품 근거가 없으면 adjacent/meta row는 boundary case로 유지해야 한다.",
            },
        ),
    ]
)

LABEL_RANK = {"REJECT": 0, "REPROCESS": 1, "HOLD": 2, "INFO_MISSING": 3, "ACCEPT": 4}
ACTION_RANK = {"re_run": 0, "re_judge": 1, "re_search": 2, "slang_db_review": 3, "human_review": 4, "docs_issue": 5}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def iter_json_array(path: Path) -> Iterable[dict[str, Any]]:
    decoder = json.JSONDecoder()
    chunk_size = 1024 * 1024 * 4
    with path.open("r", encoding="utf-8") as f:
        buf = ""
        pos = 0
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                return
            buf += chunk
            start = buf.find("[")
            if start >= 0:
                pos = start + 1
                break
            buf = ""

        while True:
            while True:
                while pos < len(buf) and buf[pos] in " \t\r\n,":
                    pos += 1
                if pos < len(buf):
                    break
                more = f.read(chunk_size)
                if not more:
                    return
                buf = ""
                pos = 0
                buf += more

            if buf[pos] == "]":
                return

            try:
                row, end = decoder.raw_decode(buf, pos)
            except json.JSONDecodeError:
                more = f.read(chunk_size)
                if not more:
                    raise
                buf = buf[pos:] + more
                pos = 0
                continue

            pos = end
            if isinstance(row, dict):
                yield row

            if pos > chunk_size:
                buf = buf[pos:]
                pos = 0


def clean_text(value: Any, limit: int = 260) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        text = " / ".join(clean_text(item, limit=limit) for item in value[:3])
    elif isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def merge_packet_label(
    labels: list[dict[str, Any]], packets: list[dict[str, Any]], action_queue: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    packet_by_id = {row.get("packet_id"): row for row in packets}
    queue_by_id = {row.get("packet_id"): row for row in action_queue}
    merged = []
    for label in labels:
        if label.get("label") == "ACCEPT":
            continue
        packet = packet_by_id.get(label.get("packet_id"), {})
        queue = queue_by_id.get(label.get("packet_id"), {})
        merged.append(
            {
                **label,
                "priority": queue.get("priority") or priority_for(label),
                "rationale": queue.get("rationale") or label.get("evidence_alignment"),
                "title": packet.get("title"),
                "body_excerpt": packet.get("body_excerpt"),
                "comment_excerpt": packet.get("comment_excerpt"),
                "resolved_title": packet.get("resolved_title"),
                "relevance": packet.get("relevance"),
                "final_decision_fields": packet.get("final_decision_fields"),
                "search_health_flags": packet.get("search_health_flags") or [],
                "risk_tags": packet.get("risk_tags") or [],
                "slang_db_fields": packet.get("slang_db_fields") or {},
                "vlm_ocr_fields": packet.get("vlm_ocr_fields") or {},
                "worker": packet.get("worker"),
                "shard": packet.get("shard"),
                "timestamp": packet.get("timestamp"),
                "source_path": packet.get("source_path"),
                "line_number": packet.get("line_number") or label.get("row_index"),
            }
        )
    return merged


def priority_for(row: dict[str, Any]) -> str:
    if row.get("label") == "REJECT":
        return "P0/P1"
    if row.get("label") == "REPROCESS" or row.get("action") in {"re_run", "re_judge", "re_search"}:
        return "P1"
    return "P2"


def sort_key(row: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        LABEL_RANK.get(str(row.get("label")), 9),
        ACTION_RANK.get(str(row.get("action")), 9),
        0 if str(row.get("round", "")).startswith("round2") else 1,
        str(row.get("packet_id")),
    )


def _patterns_for(row: dict[str, Any], *, include_action: bool = False) -> list[str]:
    bucket = str(row.get("bucket"))
    action = str(row.get("action"))
    names = []
    for name, definition in PATTERN_DEFINITIONS.items():
        if bucket in definition["buckets"] or (include_action and action in definition["actions"]):
            names.append(name)
    return names


def select_targets(rows: list[dict[str, Any]], per_pattern: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected_by_post: dict[str, dict[str, Any]] = {}
    pattern_counts: dict[str, int] = {}
    candidates_by_pattern: dict[str, int] = {}

    def add(pattern: str, row: dict[str, Any]) -> None:
        post_id = str(row.get("post_id"))
        if post_id not in selected_by_post:
            item = dict(row)
            item["round3_primary_pattern"] = pattern
            item["round3_patterns"] = []
            item["round3_priorities"] = []
            item["round3_hypotheses"] = []
            selected_by_post[post_id] = item
        item = selected_by_post[post_id]
        if pattern not in item["round3_patterns"]:
            item["round3_patterns"].append(pattern)
            item["round3_priorities"].append(PATTERN_DEFINITIONS[pattern]["priority"])
            item["round3_hypotheses"].append(PATTERN_DEFINITIONS[pattern]["hypothesis"])
            if PATTERN_DEFINITIONS[pattern]["priority"] == "P0/P1":
                item["round3_primary_pattern"] = pattern

    # 명시 REJECT는 전부 필수 P0/P1 근거로 포함한다.
    for row in sorted((r for r in rows if r.get("label") == "REJECT"), key=sort_key):
        patterns = _patterns_for(row) or ["weak_evidence_strong_resolution"]
        for pattern in patterns:
            add(pattern, row)

    for pattern, definition in PATTERN_DEFINITIONS.items():
        candidates = [
            row
            for row in rows
            if row.get("bucket") in definition["buckets"]
        ]
        if len(candidates) < per_pattern:
            seen_posts = {str(row.get("post_id")) for row in candidates}
            candidates.extend(
                row
                for row in rows
                if row.get("action") in definition["actions"] and str(row.get("post_id")) not in seen_posts
            )
        candidates = sorted(candidates, key=sort_key)
        candidates_by_pattern[pattern] = len(candidates)
        picked = 0
        for row in candidates:
            add(pattern, row)
            picked += 1
            if picked >= per_pattern:
                break
        pattern_counts[pattern] = picked

    selected = list(selected_by_post.values())
    selected.sort(key=lambda row: (str(row.get("round3_primary_pattern")), sort_key(row)))
    pattern_selected_after_dedupe = {
        pattern: sum(1 for row in selected if pattern in row.get("round3_patterns", []))
        for pattern in PATTERN_DEFINITIONS
    }
    serializable_patterns = {
        name: {
            **definition,
            "buckets": sorted(definition["buckets"]),
            "actions": sorted(definition["actions"]),
        }
        for name, definition in PATTERN_DEFINITIONS.items()
    }
    manifest = {
        "run_id": RUN_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "round": ROUND_NAME,
        "sample_seed": SEED,
        "selection_method": "모든 REJECT row와 P0/P1 실패 pattern별 고정 top non-ACCEPT 대표 row를 선택한다.",
        "per_pattern_target": per_pattern,
        "source_labels": "qualitative_review/20260505_214349_324347/review_labels.jsonl",
        "source_packets": "qualitative_review/20260505_214349_324347/review_packets.jsonl",
        "source_action_queue": "qualitative_review/20260505_214349_324347/action_queue.json",
        "selected_rows": len(selected),
        "selected_label_counts": dict(Counter(str(row.get("label")) for row in selected)),
        "selected_action_counts": dict(Counter(str(row.get("action")) for row in selected)),
        "selected_bucket_counts": dict(Counter(str(row.get("bucket")) for row in selected)),
        "pattern_candidate_counts": candidates_by_pattern,
        "pattern_selected_counts_before_dedupe": pattern_counts,
        "pattern_selected_counts_after_dedupe": pattern_selected_after_dedupe,
        "pattern_definitions": serializable_patterns,
        "gate": {
            "run_integrity": "REVIEW",
            "semantic_decision_quality": "NO-GO",
            "overall": "NO-GO",
            "reason": "Round 3 후보는 준비됐지만 targeted re-run/re-search/re-judge는 아직 실행되지 않았다.",
        },
    }
    return selected, manifest


def build_targeted_input(result_path: Path, selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected_by_post = {str(row.get("post_id")): row for row in selected}
    found: dict[str, dict[str, Any]] = {}
    for row in iter_json_array(result_path):
        post_id = str(row.get("post_id"))
        if post_id in selected_by_post:
            target = selected_by_post[post_id]
            found[post_id] = {
                "post_id": row.get("post_id"),
                "url": row.get("url"),
                "gallery_id": row.get("gallery_id"),
                "title": row.get("title"),
                "content": row.get("content"),
                "comments": row.get("comments"),
                "comments_raw": row.get("comments_raw"),
                "comment_metadata": row.get("comment_metadata"),
                "comment_context_lines": row.get("comment_context_lines"),
                "author": row.get("author"),
                "post_author": row.get("post_author") or row.get("author"),
                "created_at": row.get("created_at"),
                "_round3_target": {
                    "packet_id": target.get("packet_id"),
                    "primary_pattern": target.get("round3_primary_pattern"),
                    "patterns": target.get("round3_patterns"),
                    "priorities": target.get("round3_priorities"),
                    "label": target.get("label"),
                    "action": target.get("action"),
                    "bucket": target.get("bucket"),
                    "rationale": target.get("rationale"),
                },
            }
            if len(found) == len(selected_by_post):
                break
    return [found[str(row.get("post_id"))] for row in selected if str(row.get("post_id")) in found]


def write_issue_templates(path: Path, selected: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    by_pattern: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        for pattern in row.get("round3_patterns", []):
            by_pattern[str(pattern)].append(row)

    lines = [
        f"# Round 3 P0/P1 이슈 템플릿 - {RUN_ID}",
        "",
        f"생성 시각: {manifest['generated_at']}",
        "",
        "## Gate",
        "",
        "- run 정합성: `REVIEW`",
        "- 자연어 판정 품질: `NO-GO`",
        "- 종합: `NO-GO`",
        "- 상태: targeted 후보는 준비됐지만 re-search/re-judge/re-run은 아직 실행되지 않았다.",
        "",
        "## 선택 요약",
        "",
        f"- 선택 후보 수: `{manifest['selected_rows']}`",
        "- 라벨 집계: "
        + ", ".join(f"`{k}={v}`" for k, v in sorted(manifest["selected_label_counts"].items())),
        "- 액션 집계: "
        + ", ".join(f"`{k}={v}`" for k, v in sorted(manifest["selected_action_counts"].items())),
        "",
    ]
    for pattern, definition in PATTERN_DEFINITIONS.items():
        rows = by_pattern.get(pattern, [])
        lines.extend(
            [
                f"## {pattern}",
                "",
                f"- 우선순위: `{definition['priority']}`",
                f"- 가설: {definition['hypothesis']}",
                f"- 필요 근거: {definition['required_evidence']}",
                f"- 선택 예시 수: `{len(rows)}`",
                "",
                "| Packet | Post | Label | Action | Bucket | resolved_title | 근거 |",
                "| --- | ---: | --- | --- | --- | --- | --- |",
            ]
        )
        for row in rows[:12]:
            rationale = clean_text(row.get("rationale") or row.get("evidence_alignment"), 180).replace("|", "/")
            resolved = clean_text(row.get("resolved_title"), 80).replace("|", "/")
            lines.append(
                f"| `{row.get('packet_id')}` | `{row.get('post_id')}` | `{row.get('label')}` | "
                f"`{row.get('action')}` | `{row.get('bucket')}` | {resolved} | {rationale} |"
            )
        if len(rows) > 12:
            lines.append(f"| ... | ... | ... | ... | ... | ... | 추가 `{len(rows) - 12}`건은 `round3_p0p1_candidates.jsonl`에 있음 |")
        lines.append("")
        lines.extend(
            [
                "### Round 3 확인 항목",
                "",
                "- 현재 코드와 동일한 공개 field 리뷰 schema로 선택 post를 re-run 또는 re-judge 한다.",
                "- before/after `resolved_title`, `relevance`, `reason`, `search_health_flags`, `slang_db_fields`, action label을 비교한다.",
                "- 같은 실패 pattern이 여러 예시에서 반복될 때만 code 또는 docs issue로 승격한다.",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_action_plan(path: Path, selected: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    lines = [
        f"# Round 3 액션 계획 - {RUN_ID}",
        "",
        f"생성 시각: {manifest['generated_at']}",
        "",
        "## 현재 상태",
        "",
        "- Round 1, random control, Round 2 실패 유형 확장은 완료됐다.",
        "- Round 3 targeted 후보는 `round3_p0p1_candidates.jsonl`에 준비되어 있다.",
        "- targeted source row는 `round3_targeted_input.jsonl`에 준비되어 있다.",
        "- targeted re-search/re-judge/re-run 근거가 생성될 때까지 자연어 판정 품질은 `NO-GO`로 유지한다.",
        "",
        "## 실행 순서",
        "",
        "1. generic/common surface 및 reason/decision failure는 `re_judge` target을 먼저 실행한다.",
        "2. weak-evidence strong-resolution, alias recall loss, degraded-search bucket은 `re_search` target을 실행한다.",
        "3. VLM/OCR 개입 row는 `re_run` target을 실행한다.",
        "4. `slang_db_review` target을 실행하고 alias를 confirmed/pending/family/noise/display state로 분리한다.",
        "5. before/after packet을 `ACCEPT/HOLD/REPROCESS/REJECT/INFO_MISSING`로 다시 라벨링한다.",
        "",
        "## 종료에 필요한 근거",
        "",
        "- `round3_after_packets.jsonl`과 `round3_after_labels.jsonl`이 존재한다.",
        "- P0/P1 issue row가 `ACCEPT`, 명시적 `HOLD`, 또는 문서화된 code/docs issue 중 하나로 이동한다.",
        "- 마지막 두 round에서 새로운 systemic failure pattern이 나오지 않는다.",
        "- `gate_decision.md`가 `GO`, `REVIEW`, 또는 계속 `NO-GO`인 근거와 함께 갱신된다.",
        "",
        "## target 집계",
        "",
    ]
    for key, count in sorted(manifest["selected_bucket_counts"].items()):
        lines.append(f"- `{key}`: `{count}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def patch_gate_decision(path: Path, manifest: dict[str, Any]) -> None:
    text = path.read_text(encoding="utf-8")
    marker_candidates = ["\n## GO 전 필수 조건\n", "\n## Required Before GO\n"]
    marker = next((candidate for candidate in marker_candidates if candidate in text), marker_candidates[0])
    round3 = (
        "\n## Round 3 준비\n\n"
        f"- 후보 set: `round3_p0p1_candidates.jsonl`, row `{manifest['selected_rows']}`건.\n"
        "- targeted input: `round3_targeted_input.jsonl`.\n"
        "- 이슈 템플릿: `round3_issue_templates.md`.\n"
        "- 상태: 준비만 완료됐고 targeted re-run/re-search/re-judge는 아직 실행되지 않았다.\n"
    )
    if "## Round 3 준비" in text:
        text = re.sub(r"\n## Round 3 준비\n\n.*?(?=\n## (GO 전 필수 조건|Required Before GO)\n)", round3, text, flags=re.S)
    elif "## Round 3 Preparation" in text:
        text = re.sub(r"\n## Round 3 Preparation\n\n.*?(?=\n## (GO 전 필수 조건|Required Before GO)\n)", round3, text, flags=re.S)
    elif marker in text:
        text = text.replace(marker, round3 + marker)
    else:
        text += round3
    path.write_text(text, encoding="utf-8")


def patch_summary_files(review_dir: Path, manifest: dict[str, Any]) -> None:
    summary_path = review_dir / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        completion = summary.setdefault("standard_completion", {})
        completion["round3_p0p1_candidates_prepared"] = True
        completion["round3_targeted_execution_complete"] = False
        summary["round3_preparation"] = {
            "sample_seed": SEED,
            "selected_rows": manifest["selected_rows"],
            "targeted_input_rows": manifest["targeted_input_rows"],
            "label_counts": manifest["selected_label_counts"],
            "action_counts": manifest["selected_action_counts"],
            "pattern_selected_counts": manifest["pattern_selected_counts_after_dedupe"],
            "manifest_path": str((review_dir / "round3_p0p1_manifest.json").as_posix()),
            "candidate_path": str((review_dir / "round3_p0p1_candidates.jsonl").as_posix()),
            "targeted_input_path": str((review_dir / "round3_targeted_input.jsonl").as_posix()),
            "issue_template_path": str((review_dir / "round3_issue_templates.md").as_posix()),
            "status": "prepared_not_executed",
        }
        summary["gate"] = {
            "run_integrity": "REVIEW",
            "semantic_decision_quality": "NO-GO",
            "overall": "NO-GO",
        }
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sample_manifest_path = review_dir / "sample_manifest.json"
    if sample_manifest_path.exists():
        sample_manifest = json.loads(sample_manifest_path.read_text(encoding="utf-8"))
        sample_manifest["round3_preparation"] = {
            "status": "prepared_not_executed",
            "sample_seed": SEED,
            "selected_rows": manifest["selected_rows"],
            "targeted_input_rows": manifest["targeted_input_rows"],
            "output_files": [
                str((review_dir / "round3_p0p1_manifest.json").as_posix()),
                str((review_dir / "round3_p0p1_candidates.jsonl").as_posix()),
                str((review_dir / "round3_targeted_input.jsonl").as_posix()),
                str((review_dir / "round3_issue_templates.md").as_posix()),
                str((review_dir / "round3_action_plan.md").as_posix()),
            ],
            "blocking_note": "이 target들이 실제로 rerun/research/rejudge 되기 전까지 semantic quality gate는 NO-GO로 유지한다.",
        }
        sample_manifest_path.write_text(
            json.dumps(sample_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-dir", default=f"qualitative_review/{RUN_ID}")
    parser.add_argument("--result", default="server-poc/expert_result_20260505_214349_324347.json")
    parser.add_argument("--per-pattern", type=int, default=8)
    args = parser.parse_args()

    root = repo_root()
    review_dir = root / args.review_dir
    result_path = root / args.result

    labels = load_jsonl(review_dir / "review_labels.jsonl")
    packets = load_jsonl(review_dir / "review_packets.jsonl")
    action_queue = json.loads((review_dir / "action_queue.json").read_text(encoding="utf-8"))

    merged = merge_packet_label(labels, packets, action_queue)
    selected, manifest = select_targets(merged, per_pattern=args.per_pattern)
    targeted_input = build_targeted_input(result_path, selected)
    manifest["targeted_input_rows"] = len(targeted_input)
    manifest["missing_targeted_input_post_ids"] = [
        row.get("post_id")
        for row in selected
        if str(row.get("post_id")) not in {str(item.get("post_id")) for item in targeted_input}
    ]

    (review_dir / "round3_p0p1_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_jsonl(review_dir / "round3_p0p1_candidates.jsonl", selected)
    write_jsonl(review_dir / "round3_targeted_input.jsonl", targeted_input)
    write_issue_templates(review_dir / "round3_issue_templates.md", selected, manifest)
    write_action_plan(review_dir / "round3_action_plan.md", selected, manifest)
    patch_gate_decision(review_dir / "gate_decision.md", manifest)
    patch_summary_files(review_dir, manifest)

    print(
        json.dumps(
            {
                "selected_rows": len(selected),
                "targeted_input_rows": len(targeted_input),
                "label_counts": manifest["selected_label_counts"],
                "action_counts": manifest["selected_action_counts"],
                "output_dir": str(review_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
