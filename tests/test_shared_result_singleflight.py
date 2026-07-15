from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from llm_batch.runtime.local_stage_gate import FileSingleflightLease, StageGateTimeout, StageSingleflightKey
from llm_batch.runtime.shared_cache_contract import CacheNamespace, FileSharedCacheAdapter
from llm_batch.runtime.shared_result_singleflight import FileSharedResultSingleflight


class SharedResultSingleflightTests(unittest.TestCase):
    def _namespace(self) -> CacheNamespace:
        return CacheNamespace("a" * 64, "scope", "b" * 64, "provider", "model", "c" * 64)

    def _key(self) -> StageSingleflightKey:
        return StageSingleflightKey("a" * 64, "scope", "b" * 64, "stage", "provider", "model", "c" * 64)

    def _coordinator(self, root: Path, *, enabled: bool = True) -> FileSharedResultSingleflight:
        return FileSharedResultSingleflight(FileSharedCacheAdapter(root / "cache", allow_write=True), FileSingleflightLease(root / "lease"), enabled=enabled)

    def test_disabled_is_no_op_and_mixed_namespace_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            value, receipt = self._coordinator(Path(directory), enabled=False).run(self._namespace(), self._key(), lambda: calls.append(1) or {"value": 1}, ttl_seconds=1, follower_timeout_ms=10, lease_timeout_ms=10)
            self.assertEqual((value, calls, receipt.outcome, receipt.execution_scope), ({"value": 1}, [1], "DISABLED_NO_OP", "CROSS_PROCESS_FILE_SHARED_RESULT_SHADOW_ONLY"))
            mismatched = CacheNamespace("d" * 64, "scope", "b" * 64, "provider", "model", "c" * 64)
            with self.assertRaisesRegex(ValueError, "exact RunSpec"):
                self._coordinator(Path(directory)).run(mismatched, self._key(), lambda: {"bad": True}, ttl_seconds=1, follower_timeout_ms=10, lease_timeout_ms=10)

    def test_duplicate_threads_share_leader_result_and_follower_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); leader = self._coordinator(root); follower = self._coordinator(root); started = threading.Event(); release = threading.Event(); calls = []; results = []
            def produce() -> dict:
                calls.append("leader"); started.set(); release.wait(1); return {"producer": "leader"}
            thread = threading.Thread(target=lambda: results.append(leader.run(self._namespace(), self._key(), produce, ttl_seconds=5, follower_timeout_ms=500, lease_timeout_ms=1000)))
            thread.start(); self.assertTrue(started.wait(1))
            follow = threading.Thread(target=lambda: results.append(follower.run(self._namespace(), self._key(), lambda: calls.append("follower") or {"producer": "follower"}, ttl_seconds=5, follower_timeout_ms=500, lease_timeout_ms=1000)))
            follow.start(); time.sleep(.04); release.set(); thread.join(2); follow.join(2)
            self.assertEqual(calls, ["leader"]); self.assertTrue(all(not item.is_alive() for item in (thread, follow)))
            self.assertEqual({result[0]["producer"] for result in results}, {"leader"}); self.assertIn("FOLLOWER_HIT", {result[1].outcome for result in results})

    def test_child_leader_result_is_reused_by_parent_follower(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source_root = str(Path(__file__).resolve().parents[1] / "src"); env = dict(os.environ); env["PYTHONPATH"] = source_root + os.pathsep + env.get("PYTHONPATH", "")
            code = "import json,sys,time; from pathlib import Path; from llm_batch.runtime.local_stage_gate import FileSingleflightLease,StageSingleflightKey; from llm_batch.runtime.shared_cache_contract import CacheNamespace,FileSharedCacheAdapter; from llm_batch.runtime.shared_result_singleflight import FileSharedResultSingleflight; r=Path(sys.argv[1]); n=CacheNamespace('a'*64,'scope','b'*64,'provider','model','c'*64); k=StageSingleflightKey('a'*64,'scope','b'*64,'stage','provider','model','c'*64); c=FileSharedResultSingleflight(FileSharedCacheAdapter(r/'cache',allow_write=True),FileSingleflightLease(r/'lease'),enabled=True); v,x=c.run(n,k,lambda:(time.sleep(.15),{'producer':'child'})[1],ttl_seconds=5,follower_timeout_ms=500,lease_timeout_ms=1000); print(json.dumps({'value':v,'outcome':x.outcome}))"
            child = subprocess.Popen([sys.executable, "-c", code, str(root)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
            lease_path = root / "lease" / f"{self._key().key()}.lease.json"; deadline = time.monotonic() + 2
            while not lease_path.is_file() and time.monotonic() < deadline: time.sleep(.01)
            self.assertTrue(lease_path.is_file(), "child did not acquire lease")
            try:
                value, receipt = self._coordinator(root).run(self._namespace(), self._key(), lambda: self.fail("parent must be follower"), ttl_seconds=5, follower_timeout_ms=500, lease_timeout_ms=1000)
                stdout, stderr = child.communicate(timeout=3)
            finally:
                if child.poll() is None: child.kill(); child.communicate(timeout=3)
            self.assertEqual(child.returncode, 0, stderr); self.assertEqual(json.loads(stdout)["value"], {"producer": "child"})
            self.assertEqual((value, receipt.role, receipt.outcome), ({"producer": "child"}, "FOLLOWER", "FOLLOWER_HIT"))

    def test_late_leader_result_is_discarded_after_lease_expiry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            coordinator = self._coordinator(Path(directory))
            with self.assertRaisesRegex(StageGateTimeout, "lease expired"):
                coordinator.run(self._namespace(), self._key(), lambda: (time.sleep(.03), {"late": True})[1], ttl_seconds=5, follower_timeout_ms=20, lease_timeout_ms=10)
            self.assertEqual(coordinator.cache.get(self._namespace())["status"], "MISS")

    def test_follower_timeout_and_leader_failure_do_not_poison_next_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); coordinator = self._coordinator(root); held = FileSingleflightLease(root / "lease").acquire(self._key(), timeout_ms=5, lease_timeout_ms=500)
            with self.assertRaises(StageGateTimeout) as caught:
                coordinator.run(self._namespace(), self._key(), lambda: self.fail("follower must not run"), ttl_seconds=5, follower_timeout_ms=20, lease_timeout_ms=500)
            self.assertEqual((caught.exception.receipt.role, caught.exception.receipt.outcome), ("FOLLOWER", "TIMEOUT")); self.assertTrue(FileSingleflightLease(root / "lease").release(held))
            with self.assertRaisesRegex(RuntimeError, "producer failure"):
                coordinator.run(self._namespace(), self._key(), lambda: (_ for _ in ()).throw(RuntimeError("producer failure")), ttl_seconds=5, follower_timeout_ms=20, lease_timeout_ms=500)
            value, receipt = coordinator.run(self._namespace(), self._key(), lambda: {"recovered": True}, ttl_seconds=5, follower_timeout_ms=20, lease_timeout_ms=500)
            self.assertEqual((value, receipt.outcome), ({"recovered": True}, "PRODUCED"))


if __name__ == "__main__":
    unittest.main()
