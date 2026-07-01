import json
import tempfile
import unittest
from pathlib import Path

from tools.build_browser_visual_targets_from_result import build_targets


class BrowserVisualTargetsFromResultTest(unittest.TestCase):
    def test_builds_all_missing_browser_visual_targets_not_just_issue_samples(self):
        rows = []
        for idx in range(12):
            rows.append(
                {
                    "post_id": 1000 + idx,
                    "title": f"image post {idx}",
                    "url": f"https://example.test/{idx}",
                    "content_blocks": [{"type": "image", "url": f"https://img.test/{idx}.jpg"}],
                    "image_count": 1,
                    "analysis_result": {
                        "identity": {
                            "is_relevant": True,
                            "discussion_type": "review",
                            "title_resolution_state": "resolved",
                            "novel_identity": {"official_title": f"작품 {idx}"},
                            "context_sources": ["title", "image"],
                            "image_evidence_catalog": [
                                {
                                    "source_url": f"https://img.test/{idx}.jpg",
                                    "snippet": "image evidence",
                                }
                            ],
                            "reason": "이미지 OCR 근거가 있어 브라우저 확인 필요",
                        }
                    },
                }
            )
        rows.append(
            {
                "post_id": 2000,
                "title": "already verified",
                "content_blocks": [{"type": "image", "url": "https://img.test/ok.jpg"}],
                "image_count": 1,
                "analysis_result": {
                    "identity": {
                        "is_relevant": True,
                        "context_sources": ["image"],
                        "browser_visual_available": True,
                        "article_image_count": 1,
                        "article_loaded_count": 1,
                    }
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "result.json"
            result_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

            targets, manifest = build_targets(
                result_path,
                run_id="run-x",
                source_label="unit",
            )

        self.assertEqual(len(targets), 12)
        self.assertEqual(manifest["target_count"], 12)
        self.assertEqual(manifest["coverage"]["browser_visual_required"], 13)
        self.assertEqual(manifest["coverage"]["browser_visual_available"], 1)
        self.assertEqual(manifest["coverage"]["browser_visual_missing"], 12)
        self.assertEqual(targets[0]["issue_code"], "browser_visual_or_direct_evidence_missing")
        self.assertEqual(targets[-1]["post_id"], 1011)

    def test_external_browser_artifact_manifest_removes_verified_target(self):
        rows = [
            {
                "post_id": 11718049,
                "title": "fallback verified",
                "content_blocks": [{"type": "image", "url": "https://img.test/a.jpg"}],
                "image_count": 1,
                "analysis_result": {
                    "identity": {
                        "context_sources": ["image"],
                        "image_evidence_catalog": [{"source_url": "https://img.test/a.jpg", "snippet": "image"}],
                    }
                },
            },
            {
                "post_id": 11718068,
                "title": "still missing",
                "content_blocks": [{"type": "image", "url": "https://img.test/b.jpg"}],
                "image_count": 1,
                "analysis_result": {
                    "identity": {
                        "context_sources": ["image"],
                        "image_evidence_catalog": [{"source_url": "https://img.test/b.jpg", "snippet": "image"}],
                    }
                },
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path = root / "result.json"
            result_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            screenshot = root / "shot.png"
            screenshot.write_bytes(b"fake")
            manifest_path = root / "attempt_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "fallback_browser": {
                            "used": True,
                            "post_id": 11718049,
                            "screenshot_path": "shot.png",
                            "evidence_grade": "Medium",
                            "article_image_count": 1,
                            "article_loaded_count": 1,
                            "article_incomplete_count": 0,
                            "article_broken_count": 0,
                            "article_lazy_pending_count": 0,
                            "placeholder_current_src_count": 0,
                            "visible_observation": "본문 이미지 표시",
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            from tools.build_browser_visual_targets_from_result import load_browser_artifacts

            targets, manifest = build_targets(
                result_path,
                run_id="run-x",
                source_label="unit",
                browser_artifacts=load_browser_artifacts(manifest_path),
                browser_artifacts_manifest=manifest_path,
            )

        self.assertEqual(manifest["target_count"], 1)
        self.assertEqual(manifest["coverage"]["browser_visual_required"], 2)
        self.assertEqual(manifest["coverage"]["browser_visual_available"], 1)
        self.assertEqual(manifest["coverage"]["browser_visual_missing"], 1)
        self.assertEqual(manifest["external_browser_artifact_rows"], 1)
        self.assertEqual(targets[0]["post_id"], 11718068)

    def test_external_browser_artifact_without_loading_counters_keeps_target(self):
        rows = [
            {
                "post_id": 11718049,
                "title": "fallback screenshot only",
                "content_blocks": [{"type": "image", "url": "https://img.test/a.jpg"}],
                "image_count": 1,
                "analysis_result": {
                    "identity": {
                        "context_sources": ["image"],
                        "image_evidence_catalog": [{"source_url": "https://img.test/a.jpg", "snippet": "image"}],
                    }
                },
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path = root / "result.json"
            result_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            screenshot = root / "shot.png"
            screenshot.write_bytes(b"fake")
            manifest_path = root / "attempt_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": 11718049,
                                "screenshot_path": "shot.png",
                                "evidence_grade": "Medium",
                                "visible_observation": "본문 이미지 표시",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            from tools.build_browser_visual_targets_from_result import load_browser_artifacts

            targets, manifest = build_targets(
                result_path,
                run_id="run-x",
                source_label="unit",
                browser_artifacts=load_browser_artifacts(manifest_path),
                browser_artifacts_manifest=manifest_path,
            )

        self.assertEqual(manifest["target_count"], 1)
        self.assertEqual(manifest["coverage"]["browser_visual_required"], 1)
        self.assertEqual(manifest["coverage"]["browser_visual_available"], 0)
        self.assertEqual(manifest["coverage"]["browser_visual_missing"], 1)
        self.assertEqual(manifest["external_browser_artifact_rows"], 0)
        self.assertEqual(targets[0]["post_id"], 11718049)


if __name__ == "__main__":
    unittest.main()
