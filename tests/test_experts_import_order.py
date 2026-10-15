"""CLI를 먼저 import하지 않은 프로세스에서도 원문 유틸리티를 읽는다."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("prefix", ["llm_batch", "src.llm_batch"])
def test_grounding_import_is_independent_of_expert_cli(prefix):
    script = f"""
import importlib, sys
p={prefix!r}
m=importlib.import_module(p+'.grounding.anticipation_search_probe')
assert callable(m.source_bound_alias_assertion)
assert p+'.experts.verifier' not in sys.modules
importlib.import_module(p+'.grounding.munpia_fanart_alias_probe')
experts=importlib.import_module(p+'.experts')
assert experts.GatekeeperExpert is importlib.import_module(p+'.experts.gatekeeper').GatekeeperExpert
assert 'expert_main' not in sys.modules
"""
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT/'src')]))
    result = subprocess.run([sys.executable, '-B', '-c', script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
