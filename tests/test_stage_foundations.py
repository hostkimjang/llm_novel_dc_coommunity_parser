from __future__ import annotations

import threading
import time
import unittest
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile

from llm_batch.local_stage_gate import FileSingleflightLease, LocalSingleflight, LocalTokenBucket, StageGateTimeout, StageLimiterConfig, StageLimiterRegistry, StageSingleflightKey
from llm_batch.shared_cache_contract import CacheNamespace, ReadOnlySharedCacheAdapter, SharedCacheContractError
from llm_batch.stage_budget import ArtifactRef, StageBudgetBinding, StageBudgetError, build_shadow_stage_budget_receipt, build_stage_budget_snapshot, read_stage_budget_receipt


class StageFoundationTests(unittest.TestCase):
    def _binding(self, root: Path) -> StageBudgetBinding:
        paths = []
        for name in ("run_spec.json", "scope.json", "attempt.json", "ledger.json"):
            path = root / name; path.write_text(json.dumps({"name": name}), encoding="utf-8"); paths.append(ArtifactRef.snapshot(path))
        return StageBudgetBinding(*paths)

    def test_bound_shadow_receipt_independent_reader_and_tamper_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            binding = self._binding(Path(directory))
            receipt = build_shadow_stage_budget_receipt(binding, [{"stage": "search", "provider": "mcp", "outcome": "SUCCESS", "wait_ms": 2}])
            self.assertEqual(read_stage_budget_receipt(receipt)["independent_readback"], "GO_BOUND_SCHEMA_ONLY")
            tampered = dict(receipt); tampered["event_count"] = 99
            with self.assertRaises(StageBudgetError): read_stage_budget_receipt(tampered)
            tampered = json.loads(json.dumps(receipt)); tampered["events"][0]["wait_ms"] = float("nan")
            with self.assertRaises(StageBudgetError): read_stage_budget_receipt(tampered)

    def test_bound_reader_rejects_mixed_or_changed_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            other = self._binding(Path(second))
            for binding_name in ("run_spec", "publication_scope", "attempt"):
                receipt = build_shadow_stage_budget_receipt(self._binding(Path(first)), [])
                receipt["binding"][binding_name] = other.to_dict()[binding_name]
                with self.assertRaises(StageBudgetError):
                    read_stage_budget_receipt(receipt)
            receipt = build_shadow_stage_budget_receipt(self._binding(Path(first)), [])
            Path(receipt["binding"]["decision_ledger"]["path"]).write_text("changed", encoding="utf-8")
            with self.assertRaises(StageBudgetError): read_stage_budget_receipt(receipt)
            receipt = build_shadow_stage_budget_receipt(self._binding(Path(first)), [])
            receipt["snapshot_sha256"] = "0" * 64
            with self.assertRaises(StageBudgetError):
                read_stage_budget_receipt(receipt)
    def test_read_only_stage_budget_schema(self) -> None:
        snapshot = build_stage_budget_snapshot([{"stage": "search", "provider": "mcp", "outcome": "SUCCESS", "retries": 1, "cache_source": "DEGRADED_EXCLUDED", "wait_ms": 4, "inflight_deduped": True, "limiter_outcome": "WAITED"}])
        self.assertEqual(snapshot["mode"], "READ_ONLY_NOT_WIRED")
        self.assertEqual(snapshot["stage_provider"][0]["retries"], 1)

    def test_limiter_denies_without_wait_and_singleflight_releases_after_timeout(self) -> None:
        bucket = LocalTokenBucket(rate_per_second=1.0, burst=1)
        self.assertEqual(bucket.acquire(stage="search", provider="mcp").outcome, "ACQUIRED")
        self.assertEqual(bucket.acquire(stage="search", provider="mcp", max_wait_ms=1).outcome, "DENIED")
        gate = LocalSingleflight(); started = threading.Event(); release = threading.Event(); values = []
        leader = threading.Thread(target=lambda: values.append(gate.run("k", lambda: (started.set(), release.wait(1), "ok")[2], timeout_seconds=1)))
        leader.start(); self.assertTrue(started.wait(1))
        with self.assertRaises(StageGateTimeout): gate.run("k", lambda: "bad", timeout_seconds=0.01)
        release.set(); leader.join(1)
        self.assertEqual(gate.run("k", lambda: "next", timeout_seconds=1), ("next", False))

    def test_stale_leader_is_discarded_and_next_call_becomes_leader(self) -> None:
        gate=LocalSingleflight(); entered=threading.Event(); release=threading.Event()
        worker=threading.Thread(target=lambda: gate.run("k",lambda:(entered.set(),release.wait(1),"late")[2],timeout_seconds=1,leader_timeout_seconds=.02))
        worker.start(); self.assertTrue(entered.wait(1)); time.sleep(.03)
        self.assertEqual(gate.run("k",lambda:"fresh",timeout_seconds=1,leader_timeout_seconds=.02),("fresh",False))
        release.set(); worker.join(1)

    def test_stage_provider_registry_isolated_and_bounded(self) -> None:
        registry=StageLimiterRegistry({("search","mcp"):StageLimiterConfig(1,1,1), ("llm","provider"):StageLimiterConfig(1,1,1), ("off","x"):StageLimiterConfig(1,1,1,True)})
        self.assertEqual(registry.acquire(stage="search",provider="mcp").outcome,"ACQUIRED")
        self.assertEqual(registry.acquire(stage="search",provider="mcp").denial_reason,"MAX_WAIT_EXCEEDED")
        self.assertEqual(registry.acquire(stage="llm",provider="provider").outcome,"ACQUIRED")
        self.assertEqual(registry.acquire(stage="off",provider="x").outcome,"DISABLED")

    def test_limiter_receipt_reports_actual_wait_and_absolute_deadline(self) -> None:
        waited = StageLimiterRegistry({("search", "mcp"): StageLimiterConfig(50, 1, 500)})
        self.assertEqual(waited.acquire(stage="search", provider="mcp").outcome, "ACQUIRED")
        receipt = waited.acquire(stage="search", provider="mcp")
        self.assertEqual(receipt.outcome, "WAITED"); self.assertGreaterEqual(receipt.wait_ms, 1)
        self.assertEqual(receipt.configured_max_wait_ms, 500); self.assertFalse(receipt.deadline_exhausted)
        denied = StageLimiterRegistry({("search", "mcp"): StageLimiterConfig(1, 1, 1)})
        denied.acquire(stage="search", provider="mcp"); receipt = denied.acquire(stage="search", provider="mcp")
        self.assertEqual(receipt.outcome, "DENIED"); self.assertEqual(receipt.wait_ms, 0)
        self.assertGreater(receipt.required_wait_ms, 1); self.assertTrue(receipt.deadline_exhausted)
        self.assertEqual(receipt.execution_scope, "PROCESS_LOCAL_THREADS_ONLY")

    def test_singleflight_structured_receipts_timeout_failure_fanout_and_cleanup(self) -> None:
        gate = LocalSingleflight(); entered = threading.Event(); release = threading.Event(); leader_errors=[]; follower_errors=[]
        def fail() -> str:
            entered.set(); release.wait(1); raise RuntimeError("leader failed")
        leader = threading.Thread(target=lambda: self._capture(lambda: gate.run_with_receipt("failure", fail, timeout_seconds=1), leader_errors))
        leader.start(); self.assertTrue(entered.wait(1))
        follower = threading.Thread(target=lambda: self._capture(lambda: gate.run_with_receipt("failure", lambda: "not-used", timeout_seconds=1), follower_errors))
        follower.start(); release.set(); leader.join(1); follower.join(1)
        self.assertEqual([type(item).__name__ for item in leader_errors + follower_errors], ["RuntimeError", "RuntimeError"])
        value, receipt = gate.run_with_receipt("failure", lambda: "cleanup-ok", timeout_seconds=1)
        self.assertEqual((value, receipt.role, receipt.outcome), ("cleanup-ok", "LEADER", "SUCCESS"))
        entered = threading.Event(); release = threading.Event()
        leader = threading.Thread(target=lambda: gate.run("timeout", lambda: (entered.set(), release.wait(1), "late")[2], timeout_seconds=1))
        leader.start(); self.assertTrue(entered.wait(1))
        with self.assertRaises(StageGateTimeout) as caught:
            gate.run_with_receipt("timeout", lambda: "not-used", timeout_seconds=.01)
        self.assertEqual(caught.exception.receipt.role, "FOLLOWER"); self.assertEqual(caught.exception.receipt.outcome, "TIMEOUT")
        release.set(); leader.join(1)

    def test_scoped_singleflight_key_rejects_mixed_or_incomplete_namespace(self) -> None:
        gate = LocalSingleflight()
        first = StageSingleflightKey("a" * 64, "scope-a", "b" * 64, "search", "mcp", "model", "c" * 64)
        second = StageSingleflightKey("a" * 64, "scope-b", "b" * 64, "search", "mcp", "model", "c" * 64)
        self.assertNotEqual(first.key(), second.key())
        value, receipt = gate.run_scoped(first, lambda: "scoped", timeout_seconds=1)
        self.assertEqual((value, receipt.key_sha256), ("scoped", first.key()))
        with self.assertRaisesRegex(ValueError, "run_spec_sha256"):
            gate.run_scoped(StageSingleflightKey("A" * 64, "scope", "b" * 64, "search", "mcp", "model", "c" * 64), lambda: "bad", timeout_seconds=1)
        with self.assertRaisesRegex(ValueError, "complete RunSpec"):
            gate.run_scoped(StageSingleflightKey("a" * 64, "", "b" * 64, "search", "mcp", "model", "c" * 64), lambda: "bad", timeout_seconds=1)

    def test_file_singleflight_lease_timeout_stale_takeover_and_late_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            key = StageSingleflightKey("a" * 64, "scope", "b" * 64, "search", "mcp", "model", "c" * 64)
            first = FileSingleflightLease(Path(directory)); second = FileSingleflightLease(Path(directory))
            leader = first.acquire(key, timeout_ms=10, lease_timeout_ms=250)
            self.assertEqual((leader.role, leader.status), ("LEADER", "ACQUIRED"))
            env = dict(os.environ); env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src") + os.pathsep + env.get("PYTHONPATH", "")
            code = "import json,sys; from pathlib import Path; from llm_batch.local_stage_gate import FileSingleflightLease,StageSingleflightKey; k=StageSingleflightKey('a'*64,'scope','b'*64,'search','mcp','model','c'*64); r=FileSingleflightLease(Path(sys.argv[1])).acquire(k,timeout_ms=5,lease_timeout_ms=250); print(json.dumps({'role':r.role,'status':r.status}))"
            child = subprocess.run([sys.executable, "-c", code, directory], capture_output=True, text=True, check=True, env=env)
            self.assertEqual(json.loads(child.stdout), {"role": "FOLLOWER", "status": "TIMEOUT"})
            follower = second.acquire(key, timeout_ms=5, lease_timeout_ms=30)
            self.assertEqual((follower.role, follower.status), ("FOLLOWER", "TIMEOUT"))
            time.sleep(.27)
            replacement = second.acquire(key, timeout_ms=20, lease_timeout_ms=250)
            self.assertEqual(replacement.role, "LEADER")
            self.assertFalse(first.release(leader))
            self.assertTrue(second.release(replacement))

    def test_file_singleflight_lease_poison_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); key = StageSingleflightKey("a" * 64, "scope", "b" * 64, "search", "mcp", "model", "c" * 64)
            lease = FileSingleflightLease(root); leader = lease.acquire(key, timeout_ms=10, lease_timeout_ms=100)
            path = root / f"{key.key()}.lease.json"; value = json.loads(path.read_text(encoding="utf-8")); value["owner_token"] = "poison"; path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(StageGateTimeout, "provenance mismatch"):
                FileSingleflightLease(root).acquire(key, timeout_ms=1, lease_timeout_ms=10)
            with self.assertRaisesRegex(StageGateTimeout, "self-hash mismatch"):
                lease.release(leader)

    def test_file_singleflight_stale_follower_cannot_remove_replacement_lease(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); key = StageSingleflightKey("a" * 64, "scope", "b" * 64, "search", "mcp", "model", "c" * 64)
            stale_owner = FileSingleflightLease(root); contender = FileSingleflightLease(root); stale = stale_owner.acquire(key, timeout_ms=5, lease_timeout_ms=10)
            time.sleep(.02); observed_removal = contender._remove_expired_if_observed; replacement = []
            def interleaved(path, key_sha, observed):
                replacement.append(FileSingleflightLease(root).acquire(key, timeout_ms=30, lease_timeout_ms=200))
                return observed_removal(path, key_sha, observed)
            contender._remove_expired_if_observed = interleaved
            follower = contender.acquire(key, timeout_ms=5, lease_timeout_ms=30)
            self.assertEqual(replacement[0].role, "LEADER"); self.assertEqual(follower.role, "FOLLOWER")
            self.assertFalse(stale_owner.release(stale)); self.assertTrue(FileSingleflightLease(root).release(replacement[0]))

    @staticmethod
    def _capture(operation, errors) -> None:
        try: operation()
        except Exception as exc: errors.append(exc)

    def test_read_only_cache_and_poison_fail_closed(self) -> None:
        namespace = CacheNamespace("a" * 64, "scope", "b" * 64, "provider", "model", "c" * 64)
        cache = ReadOnlySharedCacheAdapter()
        self.assertEqual(cache.put(namespace, value={"x": 1}, ttl_seconds=1, degraded=False)["status"], "READ_ONLY")
        writable = ReadOnlySharedCacheAdapter(allow_write=True)
        stored = writable.put(namespace, value={"x": 1}, ttl_seconds=1, degraded=False)
        clone_namespace = CacheNamespace("d" * 64, "scope", "b" * 64, "provider", "model", "c" * 64)
        cached_source = {"x": 2}; stored_clone = writable.put(clone_namespace, value=cached_source, ttl_seconds=1, degraded=False); cached_source["x"] = 99
        self.assertEqual(writable.get(clone_namespace, response_sha256=stored_clone["response_sha256"])["value"], {"x": 2})
        with self.assertRaises(SharedCacheContractError): writable.get(namespace, response_sha256="wrong")
        self.assertEqual(writable.get(namespace, response_sha256=stored["response_sha256"])["status"], "HIT")
        self.assertEqual(writable.put(namespace, value={"x": 2}, ttl_seconds=1, degraded=True)["status"], "EXCLUDED_DEGRADED")
        self.assertEqual(LocalTokenBucket(rate_per_second=0, burst=1).acquire(stage="search", provider="mcp").outcome, "DENIED")
