from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from src.llm_batch.ledger.decision_ledger_binding import DecisionLedgerBindingError, build_shadow_binding, read_shadow_binding
from src.llm_batch.ledger.decision_ledger_v2 import DecisionCallLedgerV2


class DecisionLedgerBindingTests(unittest.TestCase):
    def _artifacts(self, root: Path) -> tuple[Path, Path, Path]:
        paths = []
        for name in ("run_spec", "scope", "attempt"):
            path = root / f"{name}.json"; path.write_text(json.dumps({"name": name}), encoding="utf-8"); paths.append(path)
        return tuple(paths)  # type: ignore[return-value]

    def test_cross_run_arm_scope_binding_independent_reader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); run_spec, scope, attempt = self._artifacts(root)
            ledger = DecisionCallLedgerV2(root / "ledger", scope_sha256="a" * 64)
            ledger.append_many([{"frame_kind": "INTENT", "call_id": "one"}, {"frame_kind": "TERMINAL", "call_id": "one"}])
            binding = build_shadow_binding(ledger=ledger, output_path=root / "binding.json", run_id="run-before", pair_id="pair-1", arm="BEFORE", run_spec_path=run_spec, publication_scope_path=scope, attempt_path=attempt)
            self.assertEqual(read_shadow_binding(binding)["independent_readback"], "GO_DECISION_LEDGER_V2_SHADOW_BINDING")
            self.assertEqual((binding["run_id"], binding["pair_id"], binding["arm"]), ("run-before", "pair-1", "BEFORE"))

    def test_tamper_mixed_scope_and_ledger_change_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); run_spec, scope, attempt = self._artifacts(root)
            ledger = DecisionCallLedgerV2(root / "ledger", scope_sha256="a" * 64); ledger.append({"frame_kind": "INTENT"})
            binding = build_shadow_binding(ledger=ledger, output_path=root / "binding.json", run_id="run-before", pair_id="pair-1", arm="BEFORE", run_spec_path=run_spec, publication_scope_path=scope, attempt_path=attempt)
            tampered = copy.deepcopy(binding); tampered["arm"] = "AFTER"
            with self.assertRaisesRegex(DecisionLedgerBindingError, "self-hash"):
                read_shadow_binding(tampered)
            scope.write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(DecisionLedgerBindingError, "artifact bytes"):
                read_shadow_binding(binding)
            scope.write_text(json.dumps({"name": "scope"}), encoding="utf-8")
            ledger.append({"frame_kind": "TERMINAL"})
            with self.assertRaisesRegex(DecisionLedgerBindingError, "artifact bytes|index/replay"):
                read_shadow_binding(binding)
