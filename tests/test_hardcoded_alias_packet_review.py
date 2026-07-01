from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_packet_review_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "build_hardcoded_alias_packet_review.py"
    spec = importlib.util.spec_from_file_location("build_hardcoded_alias_packet_review", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_registry_sources(root: Path) -> None:
    (root / "src/llm_batch/experts").mkdir(parents=True)
    (root / "src/llm_batch").mkdir(parents=True, exist_ok=True)
    (root / "src/llm_batch/experts/decoder.py").write_text(
        "KNOWN_ABBREVIATIONS = {'히집악': '히어로가 집착하는 악당이 되었다'}\n",
        encoding="utf-8",
    )
    (root / "src/llm_batch/experts/utils.py").write_text(
        "KNOWN_TITLE_ABBREVIATIONS = {'담텔기': '괴담 호텔 탈출기'}\n",
        encoding="utf-8",
    )
    (root / "src/llm_batch/rules.py").write_text(
        "SLANG_DICTIONARY = {'전독시': '전지적 독자 시점'}\n",
        encoding="utf-8",
    )


class HardcodedAliasPacketReviewTest(unittest.TestCase):
    def test_loads_positive_registry_entries(self) -> None:
        mod = load_packet_review_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry_sources(root)

            entries = mod.load_registry_entries(root)

        by_alias = {entry.alias: entry for entry in entries}
        self.assertEqual(by_alias["히집악"].registry, "KNOWN_ABBREVIATIONS")
        self.assertEqual(by_alias["담텔기"].registry, "KNOWN_TITLE_ABBREVIATIONS")
        self.assertEqual(by_alias["전독시"].registry, "SLANG_DICTIONARY")

    def test_scan_matches_packet_alias_and_skips_audit_reports(self) -> None:
        mod = load_packet_review_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry_sources(root)
            result = root / "out/result.json"
            report = root / "qualitative_review/v405_hardcoded_alias_risk_audit_refined.json"
            result.parent.mkdir()
            report.parent.mkdir(parents=True)
            result.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 11718120,
                            "title": "그러고보니 담텔기 작가의 말로 스포 아닌 스포했네",
                            "content": "305호 끝나면 휴재...",
                            "comments": [{"author": "ㅇㅇ", "content": "작가의 말 얘기"}],
                            "analysis_result": {
                                "identity": {
                                    "is_relevant": True,
                                    "discussion_type": "general",
                                    "novel_identity": {
                                        "official_title": "괴담 호텔 탈출기",
                                        "confidence": "High",
                                    },
                                    "reason": "slang_db/BatchContext에 확정된 약칭 담텔기 복구",
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            report.write_text(
                json.dumps({"note": "KNOWN_TITLE_ABBREVIATIONS 담텔기 self hit"}, ensure_ascii=False),
                encoding="utf-8",
            )

            payload = mod.scan_files(root, [result, report], mod.load_registry_entries(root))

        self.assertEqual(payload["summary"]["packet_coverage"], "FOUND")
        self.assertEqual(payload["summary"]["gate"], "REVIEW")
        self.assertEqual(payload["summary"]["matched_packets"], 1)
        self.assertEqual(payload["summary"]["unique_registry_match_count"], 1)
        self.assertEqual(payload["summary"]["unique_post_context_registry_match_count"], 1)
        self.assertEqual(payload["summary"]["skipped_report_files"], 1)
        self.assertEqual(
            payload["summary"]["post_context_registry_match_counts"],
            {"KNOWN_TITLE_ABBREVIATIONS": 1},
        )
        self.assertEqual(payload["summary"]["decision_context_only_registry_match_counts"], {})
        packet = payload["packets"][0]
        self.assertEqual(packet["post_id"], 11718120)
        self.assertEqual(packet["resolved_title"], "괴담 호텔 탈출기")
        self.assertEqual(packet["review_label"], "HOLD")
        self.assertEqual(packet["action"], "human_review")
        self.assertEqual(packet["alias_matches"][0]["registry"], "KNOWN_TITLE_ABBREVIATIONS")
        self.assertEqual(packet["alias_matches"][0]["alias"], "담텔기")
        self.assertTrue(packet["alias_matches"][0]["has_post_context"])
        self.assertEqual(packet["alias_matches"][0]["match_surface_scope"], "post_context")

    def test_missing_packet_coverage_requires_targeted_canary(self) -> None:
        mod = load_packet_review_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry_sources(root)
            result = root / "out/result.json"
            result.parent.mkdir()
            result.write_text(
                json.dumps([{"post_id": 1, "title": "그냥 밥 먹는 얘기", "content": "친구랑 소설 얘기"}], ensure_ascii=False),
                encoding="utf-8",
            )

            payload = mod.scan_files(root, [result], mod.load_registry_entries(root))

        self.assertEqual(payload["summary"]["packet_coverage"], "MISSING")
        self.assertEqual(payload["summary"]["gate"], "INFO_MISSING")
        self.assertEqual(payload["summary"]["semantic_approval"], "not_granted_by_packet_review")
        self.assertEqual(payload["next_actions"][0]["action"], "targeted_canary_required")

    def test_json_extension_with_jsonl_content_is_supported(self) -> None:
        mod = load_packet_review_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry_sources(root)
            result = root / "out/result.json"
            result.parent.mkdir()
            result.write_text(
                "\n".join(
                    [
                        json.dumps({"post_id": 10, "title": "그냥 이야기"}, ensure_ascii=False),
                        json.dumps({"post_id": 11, "title": "전독시 최신화 얘기"}, ensure_ascii=False),
                    ]
                ),
                encoding="utf-8",
            )

            payload = mod.scan_files(root, [result], mod.load_registry_entries(root))

        self.assertEqual(payload["summary"]["scanned_records"], 2)
        self.assertEqual(payload["summary"]["matched_packets"], 1)
        self.assertEqual(payload["summary"]["post_context_registry_match_counts"], {"SLANG_DICTIONARY": 1})

    def test_evidence_only_alias_does_not_create_packet_match(self) -> None:
        mod = load_packet_review_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry_sources(root)
            result = root / "out/result.json"
            result.parent.mkdir()
            result.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 3,
                            "title": "이게 백합 소설이 아니라니",
                            "content": "이미지 내용 이야기",
                            "analysis_result": {
                                "identity": {
                                    "novel_identity": {"official_title": "댄 이게"},
                                    "search_evidence_catalog": [
                                        {
                                            "title": "전독시 추천글",
                                            "snippet": "전지적 독자 시점 (전독시) 관련 검색 snippet",
                                        }
                                    ],
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = mod.scan_files(root, [result], mod.load_registry_entries(root))

        self.assertEqual(payload["summary"]["packet_coverage"], "MISSING")
        self.assertEqual(payload["summary"]["matched_packets"], 0)
        self.assertEqual(payload["summary"]["unique_registry_match_count"], 0)
        self.assertEqual(payload["summary"]["unique_post_context_registry_match_count"], 0)
        self.assertEqual(payload["summary"]["registry_match_counts"], {})
        self.assertEqual(payload["summary"]["post_context_registry_match_counts"], {})

    def test_decision_only_alias_is_counted_separately_from_post_context(self) -> None:
        mod = load_packet_review_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry_sources(root)
            result = root / "out/result.json"
            result.parent.mkdir()
            result.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 4,
                            "title": "305호 얘기",
                            "content": "작품 진행 얘기",
                            "analysis_result": {
                                "identity": {
                                    "slang_insight": {
                                        "detected_term": "담텔기",
                                        "decoded_term": "괴담 호텔 탈출기",
                                    },
                                    "novel_identity": {
                                        "official_title": "괴담 호텔 탈출기",
                                        "confidence": "High",
                                    },
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = mod.scan_files(root, [result], mod.load_registry_entries(root))

        self.assertEqual(payload["summary"]["packet_coverage"], "FOUND")
        self.assertEqual(payload["summary"]["registry_match_counts"], {"KNOWN_TITLE_ABBREVIATIONS": 1})
        self.assertEqual(payload["summary"]["unique_registry_match_count"], 1)
        self.assertEqual(payload["summary"]["unique_post_context_registry_match_count"], 0)
        self.assertEqual(payload["summary"]["unique_decision_context_only_registry_match_count"], 1)
        self.assertEqual(payload["summary"]["post_context_registry_match_counts"], {})
        self.assertEqual(
            payload["summary"]["decision_context_only_registry_match_counts"],
            {"KNOWN_TITLE_ABBREVIATIONS": 1},
        )
        hit = payload["packets"][0]["alias_matches"][0]
        self.assertFalse(hit["has_post_context"])
        self.assertTrue(hit["has_decision_context"])
        self.assertEqual(hit["match_surface_scope"], "decision_context")

    def test_cli_writes_json_and_korean_markdown(self) -> None:
        mod = load_packet_review_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry_sources(root)
            result = root / "out/result.json"
            output_json = root / "review.json"
            output_md = root / "review.md"
            result.parent.mkdir()
            result.write_text(
                json.dumps([{"post_id": 2, "title": "전독시 최신화 얘기"}], ensure_ascii=False),
                encoding="utf-8",
            )

            exit_code = mod.main(
                [
                    "--root",
                    str(root),
                    "--result",
                    str(result),
                    "--output-json",
                    str(output_json),
                    "--output-md",
                    str(output_md),
                ]
            )
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["summary"]["matched_packets"], 1)
        self.assertIn("# Hardcoded Alias Packet 리뷰", markdown)
        self.assertIn("semantic approval", markdown)
        self.assertIn("post-context registry match counts", markdown)


if __name__ == "__main__":
    unittest.main()
