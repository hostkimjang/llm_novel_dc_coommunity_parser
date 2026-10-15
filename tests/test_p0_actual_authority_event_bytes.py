from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from llm_batch.grounding.p0_actual_authority_contract import (  # noqa: E402
    AUTHORITY_EXAMPLE_FILES_V2,
    EXAMPLE_ORIGIN as AUTHORITY_EXAMPLE_ORIGIN,
    P0ActualAuthorityError,
    canonical_sha256,
    with_artifact_hash,
)
from llm_batch.grounding.p0_actual_authority_event_bytes import (  # noqa: E402
    verify_annotation_event_bytes,
    verify_annotation_event_bytes_from_bytes,
)
from llm_batch.grounding.p0_actual_registry_contract import (  # noqa: E402
    EXAMPLE_ORIGIN as EVENT_EXAMPLE_ORIGIN,
)
from llm_batch.grounding import p0_actual_registry_contract as registry  # noqa: E402


AUTHORITY_DIR = (
    REPO_ROOT / "tests" / "fixtures" / "p0_actual_authority_contract_example_v2"
)
EVENT_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "p0_actual_contract_example_v1"
    / "p0_annotation_events_example_v1.jsonl"
)


def _load_rows() -> dict[str, dict[str, object]]:
    return {
        logical_name: json.loads(
            (AUTHORITY_DIR / basename).read_text(encoding="utf-8")
        )
        for logical_name, basename in AUTHORITY_EXAMPLE_FILES_V2.items()
    }


class P0ActualAuthorityEventBytesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = _load_rows()
        cls.raw = EVENT_PATH.read_bytes()

    def _verify(self, *, event_path: Path = EVENT_PATH, rows=None):
        packet = self.rows if rows is None else rows
        return verify_annotation_event_bytes(
            event_path=event_path,
            predecessor_checkpoint=packet["predecessor_checkpoint"],
            predecessor_head_map=packet["predecessor_head_map"],
            current_checkpoint=packet["current_checkpoint"],
            current_head_map=packet["head_map"],
            expected_authority_origin=AUTHORITY_EXAMPLE_ORIGIN,
            expected_event_origin=EVENT_EXAMPLE_ORIGIN,
        )

    def _verify_bytes(self, *, event_bytes: bytes | None = None, rows=None):
        packet = self.rows if rows is None else rows
        return verify_annotation_event_bytes_from_bytes(
            event_bytes=self.raw if event_bytes is None else event_bytes,
            predecessor_checkpoint=packet["predecessor_checkpoint"],
            predecessor_head_map=packet["predecessor_head_map"],
            current_checkpoint=packet["current_checkpoint"],
            current_head_map=packet["head_map"],
            expected_authority_origin=AUTHORITY_EXAMPLE_ORIGIN,
            expected_event_origin=EVENT_EXAMPLE_ORIGIN,
        )

    def test_example_event_bytes_reconstruct_both_checkpoints_and_heads(self) -> None:
        receipt = self._verify()
        self.assertTrue(receipt["canonical_jsonl_verified"])
        self.assertTrue(receipt["journal_chains_verified"])
        self.assertTrue(receipt["checkpoint_prefixes_verified"])
        self.assertTrue(receipt["head_maps_reconstructed"])
        self.assertEqual(receipt["event_row_count"], 4)
        self.assertEqual(receipt["predecessor_prefix_rows"], 2)
        self.assertFalse(receipt["filesystem_handle_trust_verified"])
        self.assertFalse(receipt["durable_predecessor_verified"])
        self.assertFalse(receipt["owner_authority_verified"])
        self.assertEqual(receipt["gate_status"], "NO_GO_ACTUAL_P0_NOT_STARTED")

    def test_bytes_core_accepts_the_exact_example_bytes(self) -> None:
        receipt = self._verify_bytes()
        self.assertEqual(receipt["event_file_sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertTrue(receipt["canonical_jsonl_verified"])

    def test_bytes_core_rejects_invalid_utf8(self) -> None:
        with self.assertRaisesRegex(P0ActualAuthorityError, "strict UTF-8 JSON"):
            self._verify_bytes(event_bytes=b"\xff\n")

    def test_bytes_core_rejects_duplicate_json_keys(self) -> None:
        duplicate = self.raw.replace(
            b'"action_applied":false,',
            b'"action_applied":false,"action_applied":false,',
            1,
        )
        with self.assertRaisesRegex(P0ActualAuthorityError, "duplicate JSON key"):
            self._verify_bytes(event_bytes=duplicate)

    def test_bytes_core_rejects_noncanonical_json(self) -> None:
        with self.assertRaisesRegex(P0ActualAuthorityError, "canonical JSON"):
            self._verify_bytes(event_bytes=b"{ " + self.raw[1:])

    def test_path_wrapper_and_bytes_core_return_identical_receipts(self) -> None:
        self.assertEqual(self._verify(), self._verify_bytes())

    def test_jsonl_framing_and_canonical_bytes_fail_closed(self) -> None:
        mutations = {
            "UTF-8 BOM": b"\xef\xbb\xbf" + self.raw,
            "LF framing": self.raw.replace(b"\n", b"\r\n", 1),
            "final LF": self.raw[:-1],
            "blank rows": self.raw.replace(b"\n", b"\n\n", 1),
            "non-LF record boundary": self.raw.replace(b"\n", b"\x0b", 1),
            "canonical JSON": b"{ " + self.raw[1:],
            "non-finite constant": self.raw.replace(
                b'"journal_sequence":1', b'"journal_sequence":NaN', 1
            ),
            "duplicate JSON key": self.raw.replace(
                b'"action_applied":false,',
                b'"action_applied":false,"action_applied":false,',
                1,
            ),
        }
        for expected, raw in mutations.items():
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "events.jsonl"
                path.write_bytes(raw)
                with self.assertRaisesRegex(P0ActualAuthorityError, expected):
                    self._verify(event_path=path)

    def test_predecessor_prefix_hash_is_recomputed_from_exact_bytes(self) -> None:
        rows = deepcopy(self.rows)
        checkpoint = deepcopy(rows["predecessor_checkpoint"])
        checkpoint["prefix_sha256"] = "0" * 64
        checkpoint["event_file_sha256"] = "0" * 64
        rows["predecessor_checkpoint"] = with_artifact_hash(checkpoint)
        current = deepcopy(rows["current_checkpoint"])
        current["previous_checkpoint_sha256"] = rows["predecessor_checkpoint"][
            "artifact_sha256"
        ]
        rows["current_checkpoint"] = with_artifact_hash(current)
        with self.assertRaisesRegex(P0ActualAuthorityError, "predecessor.*hash mismatch"):
            self._verify(rows=rows)

    def test_rehashed_head_map_must_equal_event_reconstruction(self) -> None:
        rows = deepcopy(self.rows)
        head_map = deepcopy(rows["head_map"])
        head_map["heads"][0]["head_event_id"] = "EXAMPLE:FORGED:HEAD"
        head_map["head_map_sha256"] = canonical_sha256(head_map["heads"])
        rows["head_map"] = with_artifact_hash(head_map)
        current = deepcopy(rows["current_checkpoint"])
        current["prefix_head_set_sha256"] = head_map["head_map_sha256"]
        current["head_map_artifact_sha256"] = rows["head_map"]["artifact_sha256"]
        rows["current_checkpoint"] = with_artifact_hash(current)
        with self.assertRaisesRegex(P0ActualAuthorityError, "current head map reconstruction"):
            self._verify(rows=rows)

    def test_current_checkpoint_byte_count_is_recomputed(self) -> None:
        rows = deepcopy(self.rows)
        current = deepcopy(rows["current_checkpoint"])
        current["prefix_bytes"] += 1
        rows["current_checkpoint"] = with_artifact_hash(current)
        with self.assertRaisesRegex(P0ActualAuthorityError, "current checkpoint byte count"):
            self._verify(rows=rows)

    def test_checkpoint_cannot_predate_the_events_it_claims_to_seal(self) -> None:
        rows = deepcopy(self.rows)
        predecessor = deepcopy(rows["predecessor_checkpoint"])
        predecessor["created_at"] = "2026-01-01T00:00:00Z"
        rows["predecessor_checkpoint"] = with_artifact_hash(predecessor)
        current = deepcopy(rows["current_checkpoint"])
        current["previous_checkpoint_sha256"] = rows["predecessor_checkpoint"][
            "artifact_sha256"
        ]
        rows["current_checkpoint"] = with_artifact_hash(current)
        with self.assertRaisesRegex(P0ActualAuthorityError, "cannot predate"):
            self._verify(rows=rows)

    def test_file_order_must_be_prefix_closed_within_each_journal(self) -> None:
        first = json.loads(self.raw.splitlines()[0])
        second = deepcopy(first)
        second["event_id"] = "EXAMPLE:ANNOTATION_EVENT:FOLLOWUP"
        second["journal_sequence"] = 2
        second["previous_event_id"] = first["event_id"]
        second["previous_event_sha256"] = first["event_sha256"]
        second["occurred_at"] = "2026-02-01T14:00:00Z"
        second["event_sha256"] = registry._event_sha(second)
        second = registry.with_row_hash(second)

        def event_line(value):
            return (
                json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")

        raw = event_line(second) + event_line(first)

        def head(value):
            return {
                "target_record_type": value["target_record_type"],
                "target_id": value["target_id"],
                "target_subject_sha256": value["target_subject_sha256"],
                "journal_id": value["journal_id"],
                "head_sequence": value["journal_sequence"],
                "head_event_id": value["event_id"],
                "head_event_sha256": value["event_sha256"],
            }

        rows = deepcopy(self.rows)
        for logical_name, value in (
            ("predecessor_head_map", second),
            ("head_map", second),
        ):
            head_map = deepcopy(rows[logical_name])
            head_map["heads"] = [head(value)]
            head_map["head_count"] = 1
            head_map["head_map_sha256"] = canonical_sha256(head_map["heads"])
            rows[logical_name] = with_artifact_hash(head_map)
        predecessor_raw = event_line(second)
        predecessor = deepcopy(rows["predecessor_checkpoint"])
        predecessor["prefix_rows"] = 1
        predecessor["prefix_bytes"] = len(predecessor_raw)
        predecessor["prefix_sha256"] = hashlib.sha256(predecessor_raw).hexdigest()
        predecessor["event_file_sha256"] = predecessor["prefix_sha256"]
        predecessor["prefix_head_set_sha256"] = rows["predecessor_head_map"][
            "head_map_sha256"
        ]
        predecessor["head_map_artifact_sha256"] = rows[
            "predecessor_head_map"
        ]["artifact_sha256"]
        rows["predecessor_checkpoint"] = with_artifact_hash(predecessor)
        current = deepcopy(rows["current_checkpoint"])
        current["previous_checkpoint_sha256"] = rows["predecessor_checkpoint"][
            "artifact_sha256"
        ]
        current["prefix_rows"] = 2
        current["prefix_bytes"] = len(raw)
        current["prefix_sha256"] = hashlib.sha256(raw).hexdigest()
        current["event_file_sha256"] = current["prefix_sha256"]
        current["prefix_head_set_sha256"] = rows["head_map"]["head_map_sha256"]
        current["head_map_artifact_sha256"] = rows["head_map"][
            "artifact_sha256"
        ]
        rows["current_checkpoint"] = with_artifact_hash(current)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_bytes(raw)
            with self.assertRaisesRegex(P0ActualAuthorityError, "prefix-closed"):
                self._verify(event_path=path, rows=rows)

    def test_hardlink_event_path_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hardlinked = root / "events-hardlinked.jsonl"
            alias = root / "events-alias.jsonl"
            hardlinked.write_bytes(self.raw)
            try:
                alias.hardlink_to(hardlinked)
            except OSError as exc:
                self.skipTest(f"hardlink unavailable on this platform: {exc}")
            with self.assertRaisesRegex(P0ActualAuthorityError, "hard-link aliases"):
                self._verify(event_path=hardlinked)

    def test_symlink_event_path_fails_closed_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "events-target.jsonl"
            linked = root / "events-linked.jsonl"
            target.write_bytes(self.raw)
            try:
                linked.symlink_to(target)
            except OSError:
                return
            with self.assertRaisesRegex(P0ActualAuthorityError, "symlink/reparse"):
                self._verify(event_path=linked)


if __name__ == "__main__":
    unittest.main()
