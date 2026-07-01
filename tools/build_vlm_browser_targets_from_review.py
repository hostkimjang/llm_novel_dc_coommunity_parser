from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

try:
    from tools.capture_vlm_ocr_browser_review_cli import ARTICLE_IMAGE_SELECTORS
except ModuleNotFoundError:
    from capture_vlm_ocr_browser_review_cli import ARTICLE_IMAGE_SELECTORS


RUN_ID = "20260505_214349_324347"


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def post_id(value: Any) -> str:
    return str(value).strip()


def build_packet_index(review_dir: Path) -> dict[str, dict[str, Any]]:
    packet_files = [
        "round3_after_packets.jsonl",
        "round3_after_rerun_packets.jsonl",
        "round3_exit_re_search_re_run_p36_after_packets.jsonl",
    ]
    packets: dict[str, dict[str, Any]] = {}
    for name in packet_files:
        path = review_dir / name
        if not path.exists():
            continue
        for row in load_jsonl(path):
            pid = row.get("post_id")
            if pid is None:
                continue
            current = dict(row)
            current["_packet_source"] = path.as_posix()
            packets[post_id(pid)] = current
    return packets


def build_targets(review_dir: Path, labels_path: Path, output_prefix: str) -> dict[str, Any]:
    labels = load_jsonl(labels_path)
    packet_index = build_packet_index(review_dir)
    targets: list[dict[str, Any]] = []
    missing_packet_ids: list[str] = []

    for row in labels:
        if row.get("primary_pattern") != "vlm_ocr_evidence_gap":
            continue
        pid = post_id(row.get("post_id"))
        packet = packet_index.get(pid)
        if packet is None:
            missing_packet_ids.append(pid)
            packet = {}
        targets.append(
            {
                "post_id": row.get("post_id"),
                "url": packet.get("url"),
                "title": row.get("title") or packet.get("title"),
                "content": packet.get("body_excerpt"),
                "comments": packet.get("comment_excerpt"),
                "created_at": packet.get("timestamp"),
                "exit_action": "browser_visual_verify_vlm_ocr",
                "quarantine_category": "vlm_ocr_browser_gate",
                "browser_visual_required": True,
                "preferred_browser_surface": "codex_in_app_browser_iab",
                "required_article_image_selectors": ARTICLE_IMAGE_SELECTORS,
                "acceptance_gate": (
                    "본문 이미지 영역까지 스크롤한 뒤 article_image_count>0, "
                    "article_loaded_count==article_image_count, placeholder/incomplete/broken=0을 확인해야 한다."
                ),
                "primary_pattern": row.get("primary_pattern"),
                "previous_label": row.get("final_label"),
                "previous_action": row.get("final_action"),
                "previous_evidence_grade": row.get("final_evidence_grade"),
                "source_state": row.get("source_state"),
                "base_packet_id": row.get("base_packet_id"),
                "rerun_packet_id": row.get("rerun_packet_id"),
                "packet_source": packet.get("_packet_source"),
            }
        )

    # Stable dedupe by post id.
    seen: set[str] = set()
    unique_targets: list[dict[str, Any]] = []
    for row in targets:
        pid = post_id(row.get("post_id"))
        if pid in seen:
            continue
        seen.add(pid)
        unique_targets.append(row)

    out_path = review_dir / f"{output_prefix}_targets.jsonl"
    manifest_path = review_dir / f"{output_prefix}_manifest.json"
    summary_path = review_dir / f"{output_prefix}_summary_ko.md"
    write_jsonl(out_path, unique_targets)

    label_counts = Counter(str(row.get("previous_label")) for row in unique_targets)
    evidence_counts = Counter(str(row.get("previous_evidence_grade")) for row in unique_targets)
    manifest = {
        "run_id": RUN_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_labels": labels_path.as_posix(),
        "output_path": out_path.as_posix(),
        "total_vlm_ocr_targets": len(unique_targets),
        "missing_packet_ids": missing_packet_ids,
        "previous_label_counts": dict(label_counts),
        "previous_evidence_counts": dict(evidence_counts),
        "browser_gate": (
            "VLM/OCR 개입 row는 Codex 내장 브라우저에서 원문과 본문 이미지 로딩 상태를 직접 확인하기 전에는 "
            "ACCEPT로 품질 승인하지 않는다."
        ),
        "image_loading_gate": (
            "본문 이미지 선택자(.write_div .img_area/.imgwrap 중심)를 기준으로 "
            "article_image_count>0, article_loaded_count==article_image_count, "
            "article_placeholder_count/article_incomplete_count/article_broken_count=0이어야 한다."
        ),
    }
    write_json(manifest_path, manifest)

    lines = [
        "# VLM/OCR 전체 브라우저 확인 대상",
        "",
        f"- 생성 시각: `{manifest['generated_at']}`",
        f"- 대상 라벨 파일: `{labels_path.as_posix()}`",
        f"- 대상 row 수: `{len(unique_targets)}`",
        f"- packet 누락: `{len(missing_packet_ids)}`",
        "",
        "## 이전 라벨 분포",
        "",
    ]
    for key, count in sorted(label_counts.items()):
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## 이전 evidence 분포", ""])
    for key, count in sorted(evidence_counts.items()):
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(
        [
            "",
            "## 적용 gate",
            "",
            "- VLM/OCR 개입 row는 원문 URL, 이미지/evidence URL, screenshot, 시각 관찰 결과가 없으면 품질 승인에서 제외한다.",
            "- `Codex 내장 Browser plugin @browser / in-app browser iab`를 1순위 표면으로 사용한다.",
            "- 본문 이미지 영역까지 스크롤하고 `.write_div .img_area/.imgwrap` 중심 selector의 로딩 상태를 기록한다.",
            "- `article_image_count>0`, `article_loaded_count==article_image_count`, `placeholder/incomplete/broken=0`을 만족하지 못하면 `Strong`으로 보지 않는다.",
            "- 브라우저 접근 실패, 삭제, 로그인/성인 인증, 404, 차단 응답은 `Weak` 또는 `Missing` evidence로 보고 `ACCEPT`를 금지한다.",
            "- 기존 `ACCEPT` row도 시각 증거가 `Strong` 또는 충분한 `Medium`이 아니면 `REVIEW-LOCKED`로 유지한다.",
            "",
        ]
    )
    summary_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="정성 리뷰 결과에서 VLM/OCR 브라우저 확인 대상을 만든다.")
    parser.add_argument("--review-dir", default=f"qualitative_review/{RUN_ID}")
    parser.add_argument(
        "--labels",
        default=f"qualitative_review/{RUN_ID}/round3_after_rerun_combined_labels.jsonl",
    )
    parser.add_argument("--output-prefix", default="vlm_ocr_all_browser_gate")
    args = parser.parse_args()

    manifest = build_targets(Path(args.review_dir), Path(args.labels), args.output_prefix)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
