"""직접 실행된 대시보드가 저장 수령증용 tools 모듈을 찾는지 검산한다."""
import importlib.machinery
import os
from pathlib import Path
import runpy
import sys

import pytest


@pytest.mark.parametrize("outside_cwd", [False, True])
def test_direct_script_bootstrap_resolves_repository_tools_without_pythonpath(tmp_path, monkeypatch, outside_cwd):
    root = Path(__file__).resolve().parents[1]
    script = root / "tools/dashboard_server.py"
    # 파일 직접 실행처럼 sys.path[0]은 tools이며 cwd나 PYTHONPATH로 root를 보충하지 않는다.
    search = [str(root / "tools"), str(root / "src")]
    search += [p for p in sys.path if p and Path(p).resolve() != root
               and not Path(p).resolve().is_relative_to(root)]
    monkeypatch.setattr(sys, "path", search)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    monkeypatch.setenv("DASHBOARD_STANDALONE", "0")
    monkeypatch.chdir(tmp_path if outside_cwd else root)
    assert importlib.machinery.PathFinder.find_spec("tools", sys.path) is None
    # __main__을 사용하지 않아 서버/소켓을 시작하지 않는다. 실제 bootstrap 본문을 실행한다.
    namespace = runpy.run_path(str(script), run_name="dashboard_bootstrap_fixture")
    assert namespace["_REPO_ROOT"] == root
    assert os.environ["DASHBOARD_STANDALONE"] == "1"
    tools = importlib.machinery.PathFinder.find_spec("tools", sys.path)
    assert tools is not None
    assert (root / "tools").resolve() in {Path(p).resolve() for p in tools.submodule_search_locations}
    attach = importlib.machinery.PathFinder.find_spec("tools.attach_manifest_dashboard", tools.submodule_search_locations)
    assert attach is not None and Path(attach.origin).resolve() == root / "tools/attach_manifest_dashboard.py"
