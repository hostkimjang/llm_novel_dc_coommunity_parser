from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from src.llm_batch.ledger.decision_ledger_v2_mirror import read
from tools.run_decision_ledger_v2_mirror_canary import run


class DecisionLedgerV2MirrorCanaryTests(unittest.TestCase):
    def test_synthetic_canary_creates_isolated_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "canary"; value = run(output_root=root)
            self.assertEqual((value["runtime_started"], value["writes_to_production"], value["legacy_registry_write"]), (False, False, False))
            self.assertEqual(read(value)["independent_readback"], "GO_DECISION_LEDGER_V2_POSTRUN_MIRROR")
            self.assertTrue((root / "legacy" / "scope.json").is_file()); self.assertTrue((root / "mirror" / "mirror.json").is_file())


if __name__ == "__main__": unittest.main()
