from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from tools.build_stage_budget_receipt import build
from src.llm_batch.stage_budget import read_stage_budget_receipt

class StageBudgetReceiptToolTests(unittest.TestCase):
 def test_writes_independently_readable_shadow_receipt(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); files=[]
   for n in ("spec","scope","attempt","ledger"):
    p=root/(n+".json"); p.write_text("{}",encoding="utf-8"); files.append(p)
   events=root/"events.json"; events.write_text('[{"stage":"search","provider":"mcp","outcome":"SUCCESS"}]',encoding="utf-8")
   out=root/"receipt.json"; value=build(output=out,run_spec=files[0],scope=files[1],attempt=files[2],ledger=files[3],events_path=events)
   self.assertFalse(value.get("runtime_started",False)); self.assertEqual(read_stage_budget_receipt(json.loads(out.read_text(encoding="utf-8")))["independent_readback"],"GO_BOUND_SCHEMA_ONLY")
   self.assertFalse(list(root.glob(".receipt.json.*.tmp")))
