from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


RUN_ID = "20260505_214349_324347"
ROUND_NAME = "round3_targeted_after"
SEED = f"{RUN_ID}:round3_targeted_after:v1"


def _load_round2_module():
    path = Path(__file__).resolve().parent / "build_qualitative_round2_review.py"
    spec = importlib.util.spec_from_file_location("build_qualitative_round2_review", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


round2 = _load_round2_module()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_result_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        raise ValueError(f"Expected JSON array: {path}")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict) and item.get("status") and isinstance(item.get("result"), dict):
            rows.append(item["result"])
        elif isinstance(item, dict):
            rows.append(item)
    return rows


def target_map(path: Path) -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(path):
        pid = row.get("post_id")
        if pid is None:
            continue
        meta = dict(row.get("_round3_target") or {})
        if not meta.get("packet_id"):
            meta["packet_id"] = meta.get("base_packet_id") or meta.get("rerun_packet_id")
        if not meta.get("bucket"):
            meta["bucket"] = meta.get("primary_pattern") or "round3_targeted_after"
        if not meta.get("rationale"):
            meta["rationale"] = meta.get("rationale_ko") or row.get("rationale_ko")
        if not meta.get("resolved_title"):
            issue = row.get("_issue_regression") if isinstance(row.get("_issue_regression"), dict) else {}
            meta["resolved_title"] = issue.get("previous_resolved_title")
        if not meta.get("evidence_grade"):
            issue = row.get("_issue_regression") if isinstance(row.get("_issue_regression"), dict) else {}
            meta["evidence_grade"] = issue.get("previous_evidence_grade")
        meta["target_title"] = row.get("title")
        meta["target_body_excerpt"] = round2.excerpt(row.get("content"), 360)
        meta["target_comment_excerpt"] = round2.comments_excerpt(row, 360)
        targets[str(pid)] = meta
    return targets


def normalize_after_packet(
    packet: dict[str, Any],
    target: dict[str, Any],
    result_path: Path,
) -> dict[str, Any]:
    packet = dict(packet)
    packet["round"] = ROUND_NAME
    packet["sample_seed"] = SEED
    packet["source_path"] = result_path.as_posix()
    packet["result_source_path"] = result_path.as_posix()
    packet["round3_target"] = {
        "packet_id": target.get("packet_id"),
        "primary_pattern": target.get("primary_pattern"),
        "patterns": target.get("patterns") or [],
        "priorities": target.get("priorities") or [],
        "before_label": target.get("label"),
        "before_action": target.get("action"),
        "before_bucket": target.get("bucket"),
        "before_resolved_title": target.get("resolved_title"),
        "before_evidence_grade": target.get("evidence_grade"),
        "rationale": target.get("rationale"),
    }
    return packet


def _target_had_positive_alias_candidate(target: dict[str, Any]) -> bool:
    text = " ".join(
        str(value or "")
        for value in (
            target.get("rationale"),
            target.get("resolved_title"),
            target.get("evidence_grade"),
            target.get("target_title"),
        )
    ).lower()
    before_label = str(target.get("label") or "").upper()
    before_action = str(target.get("action") or "").lower()
    evidence_grade = str(target.get("evidence_grade") or "").lower()
    if before_label not in {"HOLD", "REPROCESS"}:
        return False
    if before_action not in {"re_judge", "re_search"}:
        return False
    if evidence_grade in {"weak", "missing"}:
        return False
    return bool(
        target.get("resolved_title")
        and (
            "alias" in text
            or "약칭" in text
            or "official detail" in text
            or "공식" in text
            or "url" in text
            or "positive" in text
        )
    )


def _target_has_unclosed_human_followup(target: dict[str, Any]) -> bool:
    before_label = str(target.get("label") or "").upper()
    before_action = str(target.get("action") or "").lower()
    recommended = {
        str(action or "").strip().lower()
        for action in (target.get("recommended_actions") or [])
    }
    if before_label not in {"HOLD", "REJECT", "REPROCESS"}:
        return False
    if before_action == "human_review" or recommended.intersection(
        {"human_review", "comment_url_verify"}
    ):
        return True
    text = str(target.get("rationale") or "").lower()
    return any(
        marker in text
        for marker in (
            "댓글 url",
            "댓글에 novelpia",
            "댓글에 url",
            "comment url",
            "quote",
            "source alignment",
            "human",
            "직접 답변",
            "작품 추천/답변",
        )
    )


def _apply_target_followup_guards(
    label: dict[str, Any],
    target: dict[str, Any],
    facts: dict[str, Any],
) -> dict[str, Any]:
    """Keep after-review from approving the opposite regression too early."""
    label = dict(label)
    if label.get("label") == "ACCEPT" and _target_has_unclosed_human_followup(target):
        text = str(target.get("rationale") or "").lower()
        label["label"] = "HOLD"
        label["action"] = (
            "comment_url_verify"
            if ("url" in text and ("댓글" in text or "comment" in text))
            else "human_review"
        )
        label["evidence_grade"] = "Weak"
        label["evidence_alignment"] = (
            "이전 target이 human/comment/quote 확인을 요구했으나 after 결과에는 그 확인이 닫혔다는 "
            "직접 evidence가 없다."
        )
        label["reason_quality"] = (
            "false-positive resolved title이 사라졌다는 사실과 댓글 URL 또는 기억 회수 align 검증 완료는 분리한다."
        )
        boundary = list(label.get("boundary_risk") or [])
        if "human_followup_not_closed_after_rerun" not in boundary:
            boundary.append("human_followup_not_closed_after_rerun")
        label["boundary_risk"] = boundary
        label["followup_guard"] = "human_followup_not_closed"
        return label
    if not _target_had_positive_alias_candidate(target):
        return label
    if facts.get("resolved_title"):
        return label
    idn = facts.get("identity") if isinstance(facts.get("identity"), dict) else {}
    novel_related = bool(idn.get("is_novel_related") is True or facts.get("novel_cues"))
    if not novel_related:
        return label

    label["label"] = "REJECT"
    label["action"] = "re_judge"
    label["evidence_grade"] = "Weak"
    label["evidence_alignment"] = (
        "이전 target은 alias/공식 근거 가능성이 있는 HOLD였는데, after 결과가 "
        "resolved title 없이 no-work/context-only로 닫혀 positive alias 후보를 과차단했다."
    )
    label["reason_quality"] = (
        "공식 URL이 약하거나 검색이 커뮤니티 위주라는 이유만으로 제목 선두의 순수 약칭 후보를 "
        "noise로 제거하면 false positive 차단의 반대편 회귀가 된다."
    )
    boundary = list(label.get("boundary_risk") or [])
    if "positive_alias_overblock_after_followup" not in boundary:
        boundary.append("positive_alias_overblock_after_followup")
    label["boundary_risk"] = boundary
    label["followup_guard"] = "positive_alias_candidate_overblocked"
    return label


def normalize_after_label(
    label: dict[str, Any],
    target: dict[str, Any],
    facts: dict[str, Any],
) -> dict[str, Any]:
    label = _apply_target_followup_guards(label, target, facts)
    label = dict(label)
    before_label = target.get("label")
    after_label = label.get("label")
    label["round"] = ROUND_NAME
    label["sample_seed"] = SEED
    label["before_packet_id"] = target.get("packet_id")
    label["before_label"] = before_label
    label["before_action"] = target.get("action")
    label["before_bucket"] = target.get("bucket")
    label["before_resolved_title"] = target.get("resolved_title")
    label["before_evidence_grade"] = target.get("evidence_grade")
    label["primary_pattern"] = target.get("primary_pattern")
    label["patterns"] = target.get("patterns") or []
    label["priorities"] = target.get("priorities") or []
    label["transition"] = f"{before_label}->{after_label}"
    label["reviewer_note"] = (
        "Round 3 after-target 리뷰. "
        f"before={before_label}/{target.get('action')}/{target.get('bucket')}; "
        f"after={after_label}/{label.get('action')}. "
        f"{label.get('evidence_alignment')}"
    )
    return label


def build_after_review(
    result_path: Path,
    target_input_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    targets = target_map(target_input_path)
    rows = load_result_rows(result_path)
    packets: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    missing_target_post_ids: list[str] = []

    for idx, row in enumerate(rows, 1):
        pid = str(row.get("post_id"))
        target = targets.get(pid)
        if target is None:
            target = {}
            missing_target_post_ids.append(pid)
        bucket = str(target.get("bucket") or "round3_targeted_after")
        facts = round2.extract_facts(idx, row)
        packet = round2.build_packet(f"R3A-{idx:04d}", bucket, facts, result_path)
        packet = normalize_after_packet(packet, target, result_path)
        label = round2.review_label(packet, facts)
        label = normalize_after_label(label, target, facts)
        packets.append(packet)
        labels.append(label)

    manifest = {
        "run_id": RUN_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "round": ROUND_NAME,
        "sample_seed": SEED,
        "result_path": result_path.as_posix(),
        "target_input_path": target_input_path.as_posix(),
        "result_rows": len(rows),
        "packet_rows": len(packets),
        "label_rows": len(labels),
        "target_rows": len(targets),
        "missing_target_post_ids": missing_target_post_ids,
        "post_id_dupes": len([p["post_id"] for p in packets if p.get("post_id") is not None])
        - len({str(p["post_id"]) for p in packets if p.get("post_id") is not None}),
        "label_counts": dict(Counter(str(row.get("label")) for row in labels)),
        "action_counts": dict(Counter(str(row.get("action")) for row in labels)),
        "transition_counts": dict(Counter(str(row.get("transition")) for row in labels)),
        "pattern_counts": dict(Counter(str(row.get("primary_pattern")) for row in labels)),
        "followup_guard_counts": dict(
            Counter(str(row.get("followup_guard")) for row in labels if row.get("followup_guard"))
        ),
        "content_rows": sum(1 for row in rows if row.get("content")),
        "comment_rows": sum(1 for row in rows if row.get("comments")),
    }
    return packets, labels, manifest


def write_summary(path: Path, labels: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    lines = [
        f"# Round 3 after 리뷰 - {RUN_ID}",
        "",
        f"생성 시각: {manifest['generated_at']}",
        "",
        "## 범위",
        "",
        f"- result row 수: `{manifest['result_rows']}`",
        f"- target row 수: `{manifest['target_rows']}`",
        f"- packet row 수: `{manifest['packet_rows']}`",
        f"- label row 수: `{manifest['label_rows']}`",
        f"- post id 중복 수: `{manifest['post_id_dupes']}`",
        f"- 누락된 target post id 수: `{len(manifest['missing_target_post_ids'])}`",
        f"- body content가 있는 row 수: `{manifest['content_rows']}`",
        f"- comment가 있는 row 수: `{manifest['comment_rows']}`",
        "",
        "## 라벨",
        "",
    ]
    for key, count in sorted(manifest["label_counts"].items()):
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## 액션", ""])
    for key, count in sorted(manifest["action_counts"].items()):
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## 전환", ""])
    for key, count in sorted(manifest["transition_counts"].items()):
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## Follow-up Guard", ""])
    if manifest.get("followup_guard_counts"):
        for key, count in sorted(manifest["followup_guard_counts"].items()):
            lines.append(f"- `{key}`: `{count}`")
    else:
        lines.append("- 없음")
    lines.extend(["", "## 대표 non-ACCEPT", ""])
    for row in [r for r in labels if r.get("label") != "ACCEPT"][:20]:
        lines.append(
            f"- `{row.get('packet_id')}` / post `{row.get('post_id')}` / "
            f"`{row.get('transition')}` / `{row.get('action')}` / "
            f"{row.get('evidence_alignment')}"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Round 3 after-review packet과 label을 생성한다.")
    parser.add_argument("--review-dir", default=f"qualitative_review/{RUN_ID}")
    parser.add_argument("--result", default=f"qualitative_review/{RUN_ID}/round3_after_result.json")
    parser.add_argument("--target-input", default=f"qualitative_review/{RUN_ID}/round3_targeted_input.jsonl")
    parser.add_argument("--output-prefix", default="round3_after")
    args = parser.parse_args()

    review_dir = Path(args.review_dir)
    result_path = Path(args.result)
    target_input_path = Path(args.target_input)
    packets, labels, manifest = build_after_review(result_path, target_input_path)

    prefix = args.output_prefix
    write_jsonl(review_dir / f"{prefix}_packets.jsonl", packets)
    write_jsonl(review_dir / f"{prefix}_labels.jsonl", labels)
    with (review_dir / f"{prefix}_manifest.json").open("w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    write_summary(review_dir / f"{prefix}_summary.md", labels, manifest)
    print(
        json.dumps(
            {
                "output_prefix": prefix,
                "rows": len(labels),
                "label_counts": manifest["label_counts"],
                "transition_counts": manifest["transition_counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
