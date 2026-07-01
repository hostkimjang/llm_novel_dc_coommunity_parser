from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory


def load_audit_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "audit_hardcoded_alias_risk.py"
    spec = importlib.util.spec_from_file_location("audit_hardcoded_alias_risk", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class HardcodedAliasRiskAuditTest(unittest.TestCase):
    def test_repo_audit_flags_known_positive_maps_and_quarantine_non_blocker(self) -> None:
        mod = load_audit_module()
        root = Path(__file__).resolve().parents[1]

        audit = mod.audit_paths(
            root,
            [
                Path("src/llm_batch/experts/decoder.py"),
                Path("src/llm_batch/experts/utils.py"),
                Path("src/llm_batch/batch_context.py"),
                Path("src/llm_batch/agentic_pipeline.py"),
                Path("src/llm_batch/experts/arbiter.py"),
                Path("src/llm_batch/experts/deliberation.py"),
                Path("src/llm_batch/experts/orchestrator.py"),
                Path("src/llm_batch/experts/discourse.py"),
                Path("expert_main.py"),
            ],
        )

        registries = audit["registries"]
        by_name = {item["registry_name"]: item for item in registries}
        self.assertIn("KNOWN_ABBREVIATIONS", by_name)
        self.assertIn("KNOWN_TITLE_ABBREVIATIONS", by_name)
        self.assertEqual(by_name["KNOWN_ABBREVIATIONS"]["risk_class"], "positive_resolution")
        self.assertEqual(by_name["KNOWN_TITLE_ABBREVIATIONS"]["risk_class"], "positive_resolution")
        self.assertIn(by_name["KNOWN_ABBREVIATIONS"]["gate_status"], {"REVIEW", "REVIEW-LOCKED"})
        self.assertIn(by_name["KNOWN_TITLE_ABBREVIATIONS"]["gate_status"], {"REVIEW", "REVIEW-LOCKED"})

        quarantine = next(
            item
            for item in registries
            if item["registry_name"].endswith("NON_NOVEL_MEDIA_ALIAS_SEED_BLOCKLIST")
        )
        self.assertEqual(quarantine["risk_class"], "quarantine")
        self.assertEqual(quarantine["gate_status"], "INFO")
        self.assertNotIn(
            quarantine["registry_name"],
            {item["registry_name"] for item in audit["positive_hardcoded_alias_blockers"]},
        )
        self.assertIn(audit["gate"]["semantic_approval"], {"REVIEW", "REVIEW-LOCKED"})

    def test_positive_resolution_without_guard_is_review_locked(self) -> None:
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (src / "sample.py").write_text(
                "\n".join(
                    [
                        "KNOWN_ABBREVIATIONS = {'aa': 'Alpha Alias'}",
                        "",
                        "def promote(term):",
                        "    if term in KNOWN_ABBREVIATIONS:",
                        "        full_title = KNOWN_ABBREVIATIONS[term]",
                        "        return (full_title, None, 'High', 'known_abbr')",
                        "    return None",
                    ]
                ),
                encoding="utf-8",
            )

            audit = mod.audit_paths(root, [Path("src")])

        registry = audit["registries"][0]
        self.assertEqual(registry["registry_name"], "KNOWN_ABBREVIATIONS")
        self.assertEqual(registry["scope"], "module")
        self.assertTrue(registry["positive_usage"])
        self.assertTrue(registry["usage_samples"])
        self.assertEqual(registry["usage_samples"][0]["file"], "src/sample.py")
        self.assertFalse(registry["guard_evidence_support_required"])
        self.assertEqual(registry["gate_status"], "REVIEW-LOCKED")
        self.assertEqual(audit["gate"]["semantic_approval"], "REVIEW-LOCKED")

    def test_quarantine_only_registry_is_not_approval_blocker(self) -> None:
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (src / "sample.py").write_text(
                "\n".join(
                    [
                        "class BatchContextMemory:",
                        "    NON_NOVEL_MEDIA_ALIAS_SEED_BLOCKLIST = {('aa', 'Anime Alias')}",
                        "",
                        "    def blocked(self, pair):",
                        "        return pair in self.NON_NOVEL_MEDIA_ALIAS_SEED_BLOCKLIST",
                    ]
                ),
                encoding="utf-8",
            )

            audit = mod.audit_paths(root, [Path("src")])

        registry = audit["registries"][0]
        self.assertEqual(registry["risk_class"], "quarantine")
        self.assertEqual(registry["gate_status"], "INFO")
        self.assertEqual(audit["gate"]["semantic_approval"], "GO")
        self.assertEqual(audit["gate"]["positive_hardcoded_alias_blocker_count"], 0)
        self.assertEqual(audit["gate"]["quarantine_only_count"], 1)

    def test_curated_slang_platform_and_noise_registries_are_classified(self) -> None:
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (src / "sample.py").write_text(
                "\n".join(
                    [
                        "SLANG_DICTIONARY = {'aa': ('Alpha Alias', 'source')}",
                        "PLATFORM_ABBREVIATIONS = {'ㅋㅋㅍ': '카카오페이지'}",
                        "NOISE_TERMS = {'잡담', '질문'}",
                        "",
                        "def apply(term):",
                        "    if term in SLANG_DICTIONARY:",
                        "        official_title = SLANG_DICTIONARY[term][0]",
                        "        return {'official_title': official_title, 'confidence': 'High'}",
                        "    slang = ('aa', 'Alpha Alias')",
                        "    return {'official_title': slang[1], 'confidence': 'High'}",
                        "    if term in PLATFORM_ABBREVIATIONS:",
                        "        return {'platform_hint': PLATFORM_ABBREVIATIONS[term]}",
                        "    return term not in NOISE_TERMS",
                    ]
                ),
                encoding="utf-8",
            )

            audit = mod.audit_paths(root, [Path("src")])

        by_name = {item["registry_name"]: item for item in audit["registries"]}
        self.assertEqual(by_name["SLANG_DICTIONARY"]["risk_class"], "positive_resolution")
        self.assertIn(by_name["SLANG_DICTIONARY"]["gate_status"], {"REVIEW", "REVIEW-LOCKED"})
        self.assertIn("direct_positive_return", by_name["SLANG_DICTIONARY"]["usage_kind_counts"])
        self.assertTrue(
            any(
                "official_title" in sample["text"]
                for sample in by_name["SLANG_DICTIONARY"]["usage_samples"]
            )
        )
        self.assertEqual(by_name["PLATFORM_ABBREVIATIONS"]["risk_class"], "prompt_hint")
        self.assertEqual(by_name["PLATFORM_ABBREVIATIONS"]["gate_status"], "INFO")
        self.assertEqual(by_name["NOISE_TERMS"]["risk_class"], "quarantine")
        self.assertEqual(by_name["NOISE_TERMS"]["gate_status"], "INFO")

    def test_function_scope_alias_literals_are_not_positive_registry_blockers(self) -> None:
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (src / "sample.py").write_text(
                "\n".join(
                    [
                        "def collect(term):",
                        "    alias_candidates = {'aa': 'Alpha Alias'}",
                        "    if term in alias_candidates:",
                        "        return alias_candidates[term]",
                    ]
                ),
                encoding="utf-8",
            )

            audit = mod.audit_paths(root, [Path("src")])

        registry = audit["registries"][0]
        self.assertEqual(registry["registry_name"], "alias_candidates")
        self.assertEqual(registry["scope"], "function")
        self.assertEqual(registry["risk_class"], "local_runtime_literal")
        self.assertEqual(registry["gate_status"], "INFO")
        self.assertEqual(audit["gate"]["positive_hardcoded_alias_blocker_count"], 0)
        self.assertEqual(audit["gate"]["semantic_approval"], "GO")

    def test_tooling_alias_marker_tuple_is_not_positive_registry_blocker(self) -> None:
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools = root / "tools"
            tools.mkdir()
            (tools / "build_semantic_coverage_audit.py").write_text(
                "\n".join(
                    [
                        "TITLE_ALIAS_SUPPORT_MARKERS = (",
                        "    'title_exact',",
                        "    'title_alias',",
                        "    'title_lead_alias_search_work_support',",
                        ")",
                        "",
                        "def has_support(text):",
                        "    return any(marker in text for marker in TITLE_ALIAS_SUPPORT_MARKERS)",
                    ]
                ),
                encoding="utf-8",
            )

            audit = mod.audit_paths(root, [Path("tools")])

        registry = audit["registries"][0]
        self.assertEqual(registry["registry_name"], "TITLE_ALIAS_SUPPORT_MARKERS")
        self.assertEqual(registry["file"], "tools/build_semantic_coverage_audit.py")
        self.assertEqual(registry["risk_class"], "tooling_marker")
        self.assertEqual(registry["gate_status"], "INFO")
        self.assertEqual(audit["gate"]["positive_hardcoded_alias_blocker_count"], 0)
        self.assertEqual(audit["gate"]["semantic_approval"], "GO")

    def test_official_title_none_is_not_direct_positive_usage(self) -> None:
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (src / "sample.py").write_text(
                "\n".join(
                    [
                        "SLANG_DICTIONARY = {'aa': 'Alpha Alias'}",
                        "",
                        "def apply(term):",
                        "    if term in SLANG_DICTIONARY:",
                        "        return {",
                        "            'official_title': None,",
                        "            'confidence': 'None',",
                        "            'decoded_term': SLANG_DICTIONARY[term],",
                        "        }",
                    ]
                ),
                encoding="utf-8",
            )

            audit = mod.audit_paths(root, [Path("src")])

        registry = audit["registries"][0]
        self.assertEqual(registry["registry_name"], "SLANG_DICTIONARY")
        self.assertEqual(registry["risk_class"], "positive_resolution")
        self.assertFalse(registry["positive_usage"])
        self.assertEqual(registry["positive_usage_count"], 0)
        self.assertNotIn("direct_positive_return", registry["usage_kind_counts"])
        self.assertEqual(registry["gate_status"], "INFO")
        self.assertEqual(audit["gate"]["positive_hardcoded_alias_blocker_count"], 0)

    def test_slang_dictionary_provenance_tuple_is_not_positive_usage(self) -> None:
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (src / "sample.py").write_text(
                "\n".join(
                    [
                        "SLANG_DICTIONARY = {'aa': 'Alpha Alias'}",
                        "",
                        "def collect_sources(final_title):",
                        "    confidence = 'High'",
                        "    registries = (",
                        "        (SLANG_DICTIONARY or {}, 'slang_dictionary', 'SLANG_DICTIONARY'),",
                        "    )",
                        "    return [{'source_registry': name} for _reg, _source, name in registries]",
                    ]
                ),
                encoding="utf-8",
            )

            audit = mod.audit_paths(root, [Path("src")])

        registry = audit["registries"][0]
        self.assertEqual(registry["registry_name"], "SLANG_DICTIONARY")
        self.assertFalse(registry["positive_usage"])
        self.assertEqual(registry["positive_usage_count"], 0)
        self.assertEqual(registry["gate_status"], "INFO")
        self.assertEqual(audit["gate"]["positive_hardcoded_alias_blocker_count"], 0)

    def test_known_registry_provenance_tuple_is_not_positive_usage(self) -> None:
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (src / "sample.py").write_text(
                "\n".join(
                    [
                        "KNOWN_ABBREVIATIONS = {'aa': 'Alpha Alias'}",
                        "",
                        "def collect_sources():",
                        "    registries = (",
                        "        (KNOWN_ABBREVIATIONS or {}, 'known_abbreviation', 'KNOWN_ABBREVIATIONS'),",
                        "    )",
                        "    return [{'source_registry': name} for _reg, _source, name in registries]",
                    ]
                ),
                encoding="utf-8",
            )

            audit = mod.audit_paths(root, [Path("src")])

        registry = audit["registries"][0]
        self.assertEqual(registry["registry_name"], "KNOWN_ABBREVIATIONS")
        self.assertFalse(registry["positive_usage"])
        self.assertEqual(registry["positive_usage_count"], 0)
        self.assertEqual(registry["gate_status"], "INFO")

    def test_import_only_registry_usage_is_not_positive_usage(self) -> None:
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            pkg = src / "pkg"
            pkg.mkdir(parents=True)
            (pkg / "defs.py").write_text(
                "KNOWN_ABBREVIATIONS = {'aa': 'Alpha Alias'}\n",
                encoding="utf-8",
            )
            (pkg / "use.py").write_text(
                "from .defs import KNOWN_ABBREVIATIONS\n",
                encoding="utf-8",
            )

            audit = mod.audit_paths(root, [Path("src")])

        registry = next(item for item in audit["registries"] if item["registry_name"] == "KNOWN_ABBREVIATIONS")
        self.assertFalse(registry["positive_usage"])
        self.assertEqual(registry["positive_usage_count"], 0)
        self.assertEqual(registry["gate_status"], "INFO")

    def test_tooling_registry_metadata_is_not_positive_usage(self) -> None:
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools = root / "tools"
            tools.mkdir()
            (tools / "build_hardcoded_alias_packet_review.py").write_text(
                "\n".join(
                    [
                        "REGISTRY_SOURCES = {",
                        "    'SLANG_DICTIONARY': 'src/llm_batch/rules.py',",
                        "}",
                        "REGISTRY_MARKERS = {",
                        "    'SLANG_DICTIONARY',",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            src = root / "src"
            src.mkdir()
            (src / "rules.py").write_text(
                "SLANG_DICTIONARY = {'aa': 'Alpha Alias'}\n",
                encoding="utf-8",
            )

            audit = mod.audit_paths(root, [Path("src"), Path("tools")])

        registry = next(item for item in audit["registries"] if item["registry_name"] == "SLANG_DICTIONARY")
        self.assertFalse(registry["positive_usage"])
        self.assertEqual(registry["positive_usage_count"], 0)
        self.assertEqual(registry["gate_status"], "INFO")
        self.assertEqual(audit["gate"]["positive_hardcoded_alias_blocker_count"], 0)

    def test_markdown_contains_korean_gate_guidance(self) -> None:
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (src / "sample.py").write_text(
                "KNOWN_ABBREVIATIONS = {'aa': 'Alpha Alias'}\n"
                "def f(term):\n"
                "    if term in KNOWN_ABBREVIATIONS:\n"
                "        full_title = KNOWN_ABBREVIATIONS[term]\n"
                "        return (full_title, None, 'High', 'known_abbr')\n",
                encoding="utf-8",
            )

            audit = mod.audit_paths(root, [Path("src")])
            markdown = mod.build_markdown(audit)

        self.assertIn("# Hardcoded Alias Risk 감사", markdown)
        self.assertIn("## 요약", markdown)
        self.assertIn("semantic approval", markdown)
        self.assertIn("10만 건 semantic approval을 낼 수 없습니다", markdown)

    def test_cli_writes_json_and_markdown(self) -> None:
        mod = load_audit_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            out = root / "out"
            src.mkdir()
            (src / "sample.py").write_text(
                "KNOWN_ABBREVIATIONS = {'aa': 'Alpha Alias'}\n"
                "def f(term):\n"
                "    if term in KNOWN_ABBREVIATIONS:\n"
                "        full_title = KNOWN_ABBREVIATIONS[term]\n"
                "        return (full_title, None, 'High', 'known_abbr')\n",
                encoding="utf-8",
            )
            output_json = out / "audit.json"
            output_md = out / "audit.md"

            with redirect_stdout(io.StringIO()) as stdout:
                exit_code = mod.main(
                    [
                        "--root",
                        str(root),
                        "--scan-path",
                        "src",
                        "--output-json",
                        str(output_json),
                        "--output-md",
                        str(output_md),
                        "--format",
                        "markdown",
                    ]
                )

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["gate"]["semantic_approval"], "REVIEW-LOCKED")
        self.assertIn("Registry Table", markdown)
        self.assertIn("Hardcoded Alias Risk 감사", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
