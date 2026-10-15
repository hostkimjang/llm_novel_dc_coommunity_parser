"""전용 기본 캐시와 실제 이력 탐색의 예산 분리. 모든 입력은 새 tmp에 생성한다."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from llm_batch.monitor import run_index as module
from llm_batch.monitor.run_index import RunIndex


RID = "20261013_181711_146907"


def saved_run(root, relative="recent/run/result.json", *, run_id=RID):
    output = root / relative
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps([{"post_id": 7, "run_meta": {"run_id": run_id,
        "publication_scope_id": "synthetic-scope"}}]), encoding="utf-8")
    sidecar = output.with_name(output.stem + "_manifest.json")
    sidecar.write_text(json.dumps({"output_file": str(output), "run_id": run_id,
        "publication_scope_id": "synthetic-scope", "terminal_artifacts_finalized": True,
        "completed_count": 1}), encoding="utf-8")
    return output, sidecar


def fill_cache(root, count):
    cache = root / "url_fetch_cache"
    cache.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        (cache / f"{index:064x}.json").write_text('{"cached":true}', encoding="utf-8")
    return cache


def snapshot(root):
    return {p.relative_to(root).as_posix(): (hashlib.sha256(p.read_bytes()).hexdigest(),
        p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("cache_count", [0, 64, 256])
def test_large_direct_cache_does_not_starve_nested_manifest_with_five_entry_budget(tmp_path, monkeypatch, cache_count):
    root = tmp_path / "out"
    cache = fill_cache(root, cache_count)
    output, sidecar = saved_run(root)
    before = snapshot(root)
    opened = []
    actual_scandir = module.os.scandir

    def record_scandir(path):
        opened.append(Path(path).resolve())
        return actual_scandir(path)

    monkeypatch.setattr(module.os, "scandir", record_scandir)
    index = RunIndex(max_entries=5, ttl=0)
    records = index.records(root)
    assert [r.path for r in records.values()] == [output.resolve()]
    assert next(iter(records.values())).manifest == sidecar.resolve()
    assert next(iter(records.values())).public["completion_status"] == "FINAL"
    assert index.truncated is False
    assert cache.resolve() not in opened  # 빈 캐시도 불필요하게 열거하지 않는다.
    assert snapshot(root) == before
    assert Path(module.__file__).resolve() == (ROOT / "src/llm_batch/monitor/run_index.py").resolve()


def test_cache_subtree_manifest_is_not_auto_discovered_or_counted(tmp_path):
    root = tmp_path / "out"
    fill_cache(root, 64)
    saved_run(root, "url_fetch_cache/nested/result.json", run_id="20261014_000001_000001")
    visible, _ = saved_run(root)
    before = snapshot(root)
    index = RunIndex(max_entries=5, max_manifests=1)
    assert [r.path for r in index.records(root).values()] == [visible.resolve()]
    assert index.truncated is False
    assert snapshot(root) == before


def test_same_name_below_another_directory_remains_history(tmp_path):
    root = tmp_path / "out"
    fill_cache(root, 64)
    output, _ = saved_run(root, "archive/url_fetch_cache/run/result.json")
    before = snapshot(root)
    index = RunIndex(max_entries=6)
    assert [r.path for r in index.records(root).values()] == [output.resolve()]
    assert index.truncated is False
    assert snapshot(root) == before


def test_root_itself_named_cache_is_not_globally_blacklisted(tmp_path):
    root = tmp_path / "url_fetch_cache"
    output, _ = saved_run(root)
    index = RunIndex(max_entries=4)
    assert [r.path for r in index.records(root).values()] == [output.resolve()]
    assert index.truncated is False


@pytest.mark.parametrize("limits", [
    {"max_entries": 2}, {"max_manifests": 0}, {"max_depth": 0},
])
def test_actual_history_limits_still_report_truncation(tmp_path, limits):
    root = tmp_path / "out"
    fill_cache(root, 64)
    saved_run(root)
    before = snapshot(root)
    index = RunIndex(**limits)
    assert index.records(root) == {}
    assert index.truncated is True
    assert snapshot(root) == before


def test_cache_directory_itself_still_consumes_one_entry(tmp_path):
    root = tmp_path / "out"
    fill_cache(root, 64)
    index = RunIndex(max_entries=0)
    assert index.records(root) == {}
    assert index.truncated is True


def test_non_cache_files_still_consume_budget(tmp_path):
    root = tmp_path / "out"
    fill_cache(root, 64)
    other = root / "ordinary"
    other.mkdir()
    for i in range(8):
        (other / f"{i}.json").write_text("{}", encoding="utf-8")
    index = RunIndex(max_entries=5)
    assert index.records(root) == {}
    assert index.truncated is True


def test_current_output_seed_and_resolve_survive_zero_budget_without_cache_leak(tmp_path):
    root = tmp_path / "out"
    fill_cache(root, 64)
    output, sidecar = saved_run(root, "url_fetch_cache/explicit/result.json")
    before = snapshot(root)
    index = RunIndex(max_entries=0)
    records = index.records(root, current_output=output)
    assert len(records) == 1 and index.truncated is True
    key, record = next(iter(records.items()))
    assert record.path == output.resolve() and record.manifest == sidecar.resolve()
    assert index.resolve(key, root, current_output=output).path == output.resolve()
    assert index.records(root) == {}  # 시드를 일반 탐색 캐시에 넣지 않는다.
    assert snapshot(root) == before


def test_current_output_still_requires_matching_safe_sidecar(tmp_path):
    root = tmp_path / "out"
    fill_cache(root, 64)
    output, sidecar = saved_run(root)
    other, _ = saved_run(root, "other/result.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["output_file"] = str(other)
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    outside, _ = saved_run(tmp_path / "outside")
    before = snapshot(tmp_path)
    index = RunIndex(max_entries=0)
    assert index.records(root, current_output=output) == {}
    assert index.records(root, current_output=outside) == {}
    assert snapshot(tmp_path) == before
