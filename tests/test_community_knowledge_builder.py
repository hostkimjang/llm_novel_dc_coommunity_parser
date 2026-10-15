"""로컬 원문 → 중립 parser → 세 namespace → frozen query의 계약 검증."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from llm_batch.grounding import community_knowledge_builder as builder
from llm_batch.grounding import p0_source_profile_raw_parser_core as parser_core
from llm_batch.grounding.community_knowledge import load_snapshot


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
    path.write_bytes(raw)
    return sha(raw)


def make_capture(folder, *, reviewed=True, payload=None):
    folder.mkdir(exist_ok=True)
    payload = payload if payload is not None else "'달별갤'은 달빛 기숙사라는 가상 작품을 뜻한다.\n'달별갤'은 합성 게시판 표현을 뜻한다.\n".encode("utf-8")
    (folder / "capture.txt").write_bytes(payload)
    basis = "이 파일은 저장소 시험용으로 직접 만든 합성 자료이며 로컬 복사와 파생 색인을 허용한다.\n".encode("utf-8")
    (folder / "rights.txt").write_bytes(basis)
    source = {"source_id": "synthetic-capture-1", "source_ref": "fixture://r3/synthetic-capture-1", "payload_ref": "capture.txt", "payload_byte_sha256": sha(payload),
              "capture_profile": parser_core.SUPPORTED_PROFILE, "capture_version": parser_core.SUPPORTED_CAPTURE_VERSION, "normalization_version": parser_core.SUPPORTED_NORMALIZATION_VERSION,
              "source_published_at": "2026-10-01T00:00:00Z", "source_modified_at": None, "captured_at": "2026-10-02T00:00:00Z", "available_at": "2026-10-02T00:00:00Z", "time_unknown_reason": None,
              "community_scope": ["synthetic-community-r3"], "lineage_root_id": "synthetic-lineage-1", "parent_id": None, "derivation_kind": "ORIGINAL", "lineage_status": "DECLARED",
              "rights": {"status": "SYNTHETIC_FIXTURE", "basis_ref": "rights.txt", "basis_sha256": sha(basis), "collection": True, "retention": True, "derived_index": True, "quotation": True,
                         "reviewed_at": "2026-10-02T00:00:00Z", "takedown_status": "ACTIVE"}}
    capture = {"source": source, "content_type": parser_core.SUPPORTED_CONTENT_TYPE,
               "temporal_scope": {"valid_from": "2026-10-01T00:00:00Z", "valid_to": None, "time_unknown_reason": None}, "reviews": []}
    if reviewed:
        parsed = parser_core.parse_capture(source_profile=source["capture_profile"], content_type=capture["content_type"], capture_version=source["capture_version"], normalization_version=source["normalization_version"], payload=payload)
        for index, observation in enumerate(parsed["observations"]):
            classification = {"namespace": "work_alias_registry", "work_id": "synthetic-work-1", "edition_id": "synthetic-edition-1", "media_type": "WEB_NOVEL",
                              "canonical_title": "달빛 기숙사라는 가상 작품", "canonical_title_locator": "fixture://r3/synthetic-work-1"} if index == 0 else {"namespace": "community_lexicon", "term_kind": "MEME", "competing_sense_ids": ["synthetic-work-sense"]}
            review = {"schema_version": builder.REVIEW_SCHEMA, "source_id": source["source_id"], "payload_byte_sha256": source["payload_byte_sha256"], "observation_sha256": observation["observation_sha256"],
                      "review_status": "REVIEWED", "authority": "SYNTHETIC_FIXTURE", "reviewer": "repository-synthetic-fixture-author", "sense_candidate_id": "synthetic-work-sense" if index == 0 else "synthetic-meme-sense", "classification": classification}
            filename = f"review-{index}.json"
            capture["reviews"].append({"path": filename, "sha256": dump(folder / filename, review)})
    spec = {"schema_version": builder.CAPTURE_SCHEMA, "snapshot_id": "synthetic-r3-capture-builder-v1", "data_kind": "SYNTHETIC_FIXTURE",
            "built_at": "2026-10-10T00:00:00Z", "freeze_cutoff": "2026-10-09T00:00:00Z", "captures": [capture]}
    path = folder / "captures.json"
    dump(path, spec)
    return path, spec


def query_view():
    return {"schema_version": "community_knowledge_source_view_v1", "post_id": "synthetic-builder-post", "fragments": [{"kind": "TITLE", "raw_path": "/title", "text": "달별갤"}],
            "community": {"status": "EXPLICIT", "source_path": "/gallery_id", "value": "synthetic-community-r3"},
            "as_of": {"status": "EXPLICIT", "source_path": "/created_at", "value": "2026-10-08T00:00:00Z"}}


class CommunityKnowledgeBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="r3-builder-")
        self.root = Path(self.temporary.name).resolve()
        self.inputs = self.root / "captures"
        self.spec_path, self.spec = make_capture(self.inputs)
        self.output = self.root / "snapshot"

    def tearDown(self):
        self.temporary.cleanup()

    def build(self):
        return builder.build_snapshot(self.spec_path, self.output, capture_root=self.inputs, output_root=self.root)

    def save(self):
        dump(self.spec_path, self.spec)

    def test_capture_parser_snapshot_query_namespaces_and_source_unchanged(self):
        before = {path: path.read_bytes() for path in self.inputs.iterdir()}
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            receipt = self.build()
            frozen = load_snapshot(self.output / "manifest.json", expected_sha256=receipt["snapshot_sha256"])
            result = frozen.query(query_view())
        self.assertEqual(receipt["row_counts"], {"candidate_ledger": 2, "work_alias_registry": 1, "community_lexicon": 1})
        self.assertEqual(result["status"], "AMBIGUOUS")
        self.assertEqual(len(result["candidates"]), 2)
        self.assertTrue(all(path.read_bytes() == raw for path, raw in before.items()))
        self.assertTrue(all(item["unchanged"] for item in receipt["source_integrity"]))
        self.assertFalse(result["public_authority"])
        self.assertFalse(result["central_db_write"])
        self.assertFalse(receipt["actual_semantic_evidence_verified"])

    def test_matched_definition_alone_never_creates_review_or_work_alias(self):
        self.spec_path, self.spec = make_capture(self.inputs, reviewed=False, payload="'아생갤'은 아카데미 생존 갤러리를 뜻한다.\n".encode())
        receipt = self.build()
        self.assertEqual(receipt["row_counts"], {"candidate_ledger": 1, "work_alias_registry": 0, "community_lexicon": 0})
        row = json.loads((self.output / "candidate_ledger.jsonl").read_bytes())
        self.assertEqual(row["review_status"], "UNREVIEWED")
        self.assertNotIn("review", row)

    def test_unknown_or_revoked_rights_inventory_has_no_payload_derivatives(self):
        for status in ("UNKNOWN", "REVOKED"):
            with self.subTest(status=status):
                self.output = self.root / status
                rights = self.spec["captures"][0]["source"]["rights"]
                rights["status"] = status
                rights["basis_ref"] = rights["basis_sha256"] = None
                self.save()
                receipt = self.build()
                self.assertEqual(receipt["status"], "COMPLETE_WITH_LIMITS")
                self.assertEqual(receipt["capture_inventory"][0]["disposition"], "EXCLUDED_RIGHTS")
                self.assertEqual(receipt["capture_inventory"][0]["source_metadata"]["rights"]["status"], status)
                self.assertEqual(receipt["snapshot_source_count"], 0)
                self.assertEqual(list((self.output / "payloads").iterdir()), [])

    def test_unknown_time_is_kept_unknown_and_not_query_eligible(self):
        source = self.spec["captures"][0]["source"]
        source["source_published_at"] = None
        source["time_unknown_reason"] = "합성 시험에서 원 게시 시각을 제공하지 않음"
        self.save()
        receipt = self.build()
        result = load_snapshot(self.output / "manifest.json", expected_sha256=receipt["snapshot_sha256"]).query(query_view())
        self.assertIn("TIME_UNKNOWN", receipt["capture_inventory"][0]["reason_codes"])
        self.assertFalse(receipt["capture_inventory"][0]["active_query_eligible"])
        self.assertEqual(result["candidates"], [])

    def test_unknown_review_or_sense_time_does_not_claim_query_eligibility(self):
        for field in ("reviewed_at", "valid_from"):
            with self.subTest(field=field):
                self.spec_path, self.spec = make_capture(self.inputs)
                self.output = self.root / field
                capture = self.spec["captures"][0]
                if field == "reviewed_at":
                    capture["source"]["rights"][field] = None
                else:
                    capture["temporal_scope"][field] = None
                    capture["temporal_scope"]["time_unknown_reason"] = "합성 의미의 적용 시작 시각 미제공"
                self.save()
                receipt = self.build()
                self.assertEqual(receipt["status"], "COMPLETE_WITH_LIMITS")
                self.assertFalse(receipt["capture_inventory"][0]["active_query_eligible"])
                frozen = load_snapshot(self.output / "manifest.json", expected_sha256=receipt["snapshot_sha256"])
                self.assertEqual(frozen.query(query_view())["candidates"], [])

    def test_unsupported_profile_and_nonmatching_capture_remain_inventory(self):
        for mode in ("unsupported", "nonmatching"):
            with self.subTest(mode=mode):
                self.output = self.root / mode
                self.spec_path, self.spec = make_capture(self.inputs, reviewed=False, payload=b"plain text without explicit definition")
                if mode == "unsupported":
                    self.spec["captures"][0]["source"]["capture_profile"] = "OFFICIAL_STRUCTURED"
                self.save()
                receipt = self.build()
                self.assertEqual(receipt["capture_inventory"][0]["disposition"], "UNSUPPORTED_PROFILE" if mode == "unsupported" else "NO_MATCH")
                self.assertEqual(receipt["row_counts"]["candidate_ledger"], 0)

    def test_payload_and_rights_hash_mismatch_fail_before_output(self):
        for name in ("capture.txt", "rights.txt"):
            original = (self.inputs / name).read_bytes()
            (self.inputs / name).write_bytes(original + b"changed")
            with self.subTest(name=name), self.assertRaisesRegex(builder.CommunityKnowledgeBuildError, "SOURCE_SHA256_MISMATCH"):
                self.build()
            self.assertFalse(self.output.exists())
            (self.inputs / name).write_bytes(original)

    def test_review_must_bind_exact_observation_and_payload(self):
        for key in ("observation_sha256", "payload_byte_sha256"):
            self.spec_path, self.spec = make_capture(self.inputs)
            review_path = self.inputs / self.spec["captures"][0]["reviews"][0]["path"]
            review = json.loads(review_path.read_bytes())
            review[key] = "0" * 64
            self.spec["captures"][0]["reviews"][0]["sha256"] = dump(review_path, review)
            self.save()
            with self.subTest(key=key), self.assertRaises(builder.CommunityKnowledgeBuildError):
                self.build()
            self.assertFalse(self.output.exists())

    def test_separate_parser_replay_rejects_changed_span(self):
        original = parser_core.parse_capture
        def changed(**kwargs):
            value = original(**kwargs)
            value["observations"][0]["utf8_byte_span_end"] -= 1
            return value
        with patch.object(parser_core, "parse_capture", side_effect=changed), self.assertRaisesRegex(builder.CommunityKnowledgeBuildError, "NEUTRAL_PARSER_REPLAY_FAILED"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_output_exists_and_path_escape_rejected(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("keep")
        with self.assertRaisesRegex(builder.CommunityKnowledgeBuildError, "OUTPUT_EXISTS"):
            self.build()
        self.assertEqual(sentinel.read_text(), "keep")
        self.output = self.root.parent / "outside-r3-output"
        with self.assertRaisesRegex(builder.CommunityKnowledgeBuildError, "PATH_ESCAPE"):
            self.build()

    def test_source_parent_traversal_and_symlink_rejected(self):
        self.spec["captures"][0]["source"]["payload_ref"] = "../outside.txt"
        self.save()
        with self.assertRaisesRegex(builder.CommunityKnowledgeBuildError, "SOURCE_PATH_NOT_RELATIVE"):
            self.build()
        self.spec_path, self.spec = make_capture(self.inputs)
        link = self.inputs / "link.txt"
        try:
            link.symlink_to(self.inputs / "capture.txt")
        except OSError:
            self.skipTest("Windows symlink creation privilege unavailable")
        self.spec["captures"][0]["source"]["payload_ref"] = "link.txt"
        self.save()
        with self.assertRaisesRegex(builder.CommunityKnowledgeBuildError, "SYMLINK_OR_REPARSE_FORBIDDEN"):
            self.build()

    def test_source_change_during_staging_leaves_failure_not_final_snapshot(self):
        original = builder._write_new
        changed = False
        def writing(path, raw):
            nonlocal changed
            result = original(path, raw)
            if not changed:
                changed = True
                payload = self.inputs / "capture.txt"
                payload.write_bytes(payload.read_bytes() + b"changed")
            return result
        with patch.object(builder, "_write_new", side_effect=writing):
            with self.assertRaisesRegex(builder.CommunityKnowledgeBuildError, "SOURCE_CHANGED_DURING_BUILD") as caught:
                self.build()
        self.assertFalse(self.output.exists())
        stage = Path(caught.exception.failure_directory)
        self.assertTrue((stage / "FAILED_BUILD.json").is_file())
        self.assertFalse((stage / "manifest.json").exists())

    def test_same_bytes_produce_same_snapshot_hash_in_new_directory(self):
        one = self.build()
        self.output = self.root / "snapshot-two"
        two = self.build()
        self.assertEqual(one["snapshot_sha256"], two["snapshot_sha256"])

    def test_duplicate_ids_and_json_keys_rejected(self):
        self.spec["captures"].append(deepcopy(self.spec["captures"][0]))
        self.save()
        with self.assertRaisesRegex(builder.CommunityKnowledgeBuildError, "DUPLICATE_SOURCE_ID"):
            self.build()
        self.spec_path.write_bytes(b'{"schema_version":"a","schema_version":"b"}')
        with self.assertRaisesRegex(builder.CommunityKnowledgeBuildError, "DUPLICATE_JSON_KEY"):
            self.build()

    def test_cli_build_uses_explicit_roots(self):
        cli_path = Path(__file__).resolve().parents[1] / "tools/build_community_knowledge_snapshot.py"
        spec = importlib.util.spec_from_file_location("r3_builder_cli", cli_path)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with patch("builtins.print"):
            self.assertEqual(cli.main(["--capture-manifest", str(self.spec_path), "--capture-root", str(self.inputs), "--output-dir", str(self.output), "--output-root", str(self.root)]), 0)


if __name__ == "__main__":
    unittest.main()
