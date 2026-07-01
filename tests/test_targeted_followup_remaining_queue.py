from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "build_targeted_followup_remaining_queue.py"
    spec = importlib.util.spec_from_file_location("build_targeted_followup_remaining_queue", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def result_row(post_id: int, title: str, official_title: str | None = None) -> dict:
    return {
        "post_id": post_id,
        "url": f"https://example.test/{post_id}",
        "gallery_id": "genrenovel",
        "title": title,
        "content": ["본문"],
        "comments": [{"author": "ㅇㅇ", "content": "댓글"}],
        "comment_metadata": [{"comment_id": "c1", "author": "ㅇㅇ"}],
        "comment_dialogue_context_lines": ["ㅇㅇ: 댓글"],
        "image_urls": [],
        "image_count": 0,
        "analysis_result": {
            "identity": {
                "is_relevant": bool(official_title),
                "work_resolution": "resolved" if official_title else "none",
                "discussion_type": "general",
                "topicality": "core_relevant" if official_title else "unrelated",
                "title_resolution_state": "resolved" if official_title else "unresolved",
                "title_resolution_allowed": bool(official_title),
                "anchor_type": "title_exact" if official_title else "none",
                "anchor_strength": "high" if official_title else "none",
                "reason": "테스트 reason",
                "novel_identity": {
                    "official_title": official_title,
                    "confidence": "High",
                }
                if official_title
                else None,
                "search_evidence_catalog": [
                    {
                        "eid": "E001",
                        "title": official_title or title,
                        "url": "https://novelpia.com/novel/1",
                        "domain": "novelpia.com",
                        "snippet": "공식 근거",
                        "purpose": "official_title_verify",
                        "source_tier": "novel_platform",
                    }
                ],
            }
        },
    }


class TargetedFollowupRemainingQueueTest(unittest.TestCase):
    def test_builds_hold_and_review_only_queue(self):
        mod = load_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            labels = root / "labels.jsonl"
            coverage = root / "coverage.json"
            result = root / "result.json"
            write_jsonl(
                labels,
                [
                    {
                        "post_id": 1,
                        "label": "HOLD",
                        "action": "human_review",
                        "evidence_grade": "Weak",
                        "bucket": "blocked_intent_resolved_title",
                        "reviewer_note": "확인 필요",
                    },
                    {
                        "post_id": 2,
                        "label": "ACCEPT",
                        "action": "no_action",
                        "evidence_grade": "Strong",
                    },
                ],
            )
            write_json(
                coverage,
                {
                    "issues": [
                        {
                            "code": "search_only_resolved_title_review_only",
                            "severity": "REVIEW",
                            "count": 1,
                            "sample_post_ids": [2],
                            "description": "review-only",
                            "recommended_action": "직접 근거 확인",
                        }
                    ]
                },
            )
            write_json(
                result,
                [
                    result_row(1, "잡담", None),
                    result_row(2, "작품 약칭", "작품명"),
                ],
            )

            payload = mod.build_queue(labels, coverage, result, "vtest")

        manifest = payload["manifest"]
        self.assertEqual(manifest["queue_items"], 2)
        self.assertEqual(manifest["targeted_followup_gate"], "REVIEW")
        self.assertEqual(manifest["overall_100k_semantic_gate"], "REVIEW-LOCKED")
        self.assertEqual(manifest["queue_type_counts"], {"coverage_review_only": 1, "hold_followup": 1})
        self.assertEqual({item["label"] for item in payload["queue"]}, {"HOLD", "REVIEW_ONLY"})
        self.assertEqual(len(payload["packets"]), 2)

    def test_markdown_is_korean_gate_summary(self):
        mod = load_module()
        payload = {
            "manifest": {
                "targeted_followup_gate": "REVIEW",
                "semantic_approval": "not_granted_by_targeted_followup_queue",
                "overall_100k_semantic_gate": "REVIEW-LOCKED",
                "queue_items": 1,
                "unique_posts": 1,
                "label_counts": {"HOLD": 1},
                "queue_type_counts": {"hold_followup": 1},
                "action_counts": {"human_review": 1},
            },
            "queue": [
                {
                    "post_id": 1,
                    "queue_type": "hold_followup",
                    "label": "HOLD",
                    "action": "human_review",
                    "priority": "P1",
                    "close_condition": "직접 근거 확인",
                }
            ],
        }
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "summary.md"
            mod.write_markdown(payload, out)
            text = out.read_text(encoding="utf-8")

        self.assertIn("## 요약", text)
        self.assertIn("overall_100k_semantic_gate", text)
        self.assertIn("전체 10만 건 semantic approval", text)

    def test_resolved_title_ignores_promotion_blocked_primary_work_candidate(self):
        mod = load_module()
        row = result_row(3, "후보만 보존", None)
        identity = row["analysis_result"]["identity"]
        identity.update(
            {
                "is_relevant": True,
                "candidate_ledger_status": "promotion_blocked",
                "title_resolution_allowed": False,
                "work_resolution": "unresolved",
                "primary_work": {
                    "official_title": "후보 작품",
                    "heretic_url": "https://novelpia.com/novel/382324",
                    "reference_role": "candidate",
                    "promotion_policy": "hold_without_promotion",
                    "blocked_by_candidate_audit": True,
                },
            }
        )

        self.assertIsNone(mod.resolved_title(row))
        self.assertIsNone(mod.final_decision_fields(row)["resolved_title"])

    def test_resolved_title_keeps_legacy_promoted_primary_work(self):
        mod = load_module()
        row = result_row(4, "구형 결과", None)
        identity = row["analysis_result"]["identity"]
        identity.update(
            {
                "is_relevant": True,
                "candidate_ledger_status": "safe_resolved",
                "title_resolution_allowed": True,
                "work_resolution": "resolved",
                "title_resolution_state": "resolved",
                "primary_work": {
                    "official_title": "승격 작품",
                    "heretic_url": "https://novelpia.com/novel/1",
                    "reference_role": "primary",
                },
            }
        )

        self.assertEqual(mod.resolved_title(row), "승격 작품")


if __name__ == "__main__":
    unittest.main()
