from __future__ import annotations

import math
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from llm_batch.runtime.shared_cache_contract import (
    CacheNamespace,
    ProcessSharedCacheAdapter,
    FileSharedCacheAdapter,
    ReadOnlySharedCacheAdapter,
    SharedCacheContractError,
)


class SharedCacheContractTests(unittest.TestCase):
    def _namespace(self, *, run_spec: str | None = None) -> CacheNamespace:
        return CacheNamespace(
            run_spec or "a" * 64,
            "publication-scope",
            "b" * 64,
            "provider",
            "model",
            "c" * 64,
        )

    def test_namespace_hash_fields_require_exact_lowercase_sha256(self) -> None:
        for invalid in ("a" * 63, "A" * 64, "g" * 64, " a" * 32):
            with self.subTest(invalid=invalid):
                with self.assertRaises(SharedCacheContractError):
                    self._namespace(run_spec=invalid).key()

    def test_ttl_rejects_nonpositive_and_nonfinite_numbers(self) -> None:
        cache = ReadOnlySharedCacheAdapter(allow_write=True)
        for ttl in (0, -1, math.nan, math.inf, -math.inf, True):
            with self.subTest(ttl=ttl):
                with self.assertRaises(SharedCacheContractError):
                    cache.put(self._namespace(), value={"ok": True}, ttl_seconds=ttl, degraded=False)

    def test_payload_rejects_nonfinite_values_even_when_nested_or_degraded(self) -> None:
        cache = ReadOnlySharedCacheAdapter(allow_write=True)
        for value in ({"value": math.nan}, {"nested": [math.inf]}, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(SharedCacheContractError):
                    cache.put(self._namespace(), value=value, ttl_seconds=1, degraded=False)
                with self.assertRaises(SharedCacheContractError):
                    cache.put(self._namespace(), value=value, ttl_seconds=1, degraded=True)

    def test_expired_entry_is_deleted_and_receipt_records_eviction(self) -> None:
        cache = ReadOnlySharedCacheAdapter(allow_write=True)
        namespace = self._namespace()
        with patch("llm_batch.runtime.shared_cache_contract.time.monotonic", side_effect=[10.0, 12.0]):
            stored = cache.put(namespace, value={"x": 1}, ttl_seconds=1, degraded=False)
            missed = cache.get(namespace)
        self.assertEqual(missed["status"], "MISS")
        self.assertTrue(missed["expired_entry_deleted"])
        self.assertNotIn(stored["namespace_sha256"], cache._entries)

    def test_poison_fails_closed_and_receipts_preserve_object_local_provenance(self) -> None:
        cache = ReadOnlySharedCacheAdapter(allow_write=True)
        namespace = self._namespace()
        stored = cache.put(namespace, value={"x": 1}, ttl_seconds=10, degraded=False)
        self.assertEqual(stored["adapter_scope"], "OBJECT_LOCAL")
        self.assertEqual(stored["contract_mode"], "SHADOW_ONLY_NOT_RUNTIME_WIRED")
        self.assertEqual(stored["namespace_sha256"], namespace.key())
        with self.assertRaises(SharedCacheContractError):
            cache.get(namespace, response_sha256="0" * 64)
        with self.assertRaises(SharedCacheContractError):
            cache.get(namespace, response_sha256="not-a-sha")
        hit = cache.get(namespace, response_sha256=stored["response_sha256"])
        self.assertEqual(hit["cache_source"], "OBJECT_LOCAL")
        self.assertEqual(hit["namespace_sha256"], stored["namespace_sha256"])

    def test_degraded_value_is_never_stored_and_has_provenance_receipt(self) -> None:
        cache = ReadOnlySharedCacheAdapter(allow_write=True)
        namespace = self._namespace()
        receipt = cache.put(namespace, value={"x": 1}, ttl_seconds=10, degraded=True)
        self.assertEqual(receipt["status"], "EXCLUDED_DEGRADED")
        self.assertEqual(receipt["cache_source"], "DEGRADED_EXCLUDED")
        self.assertTrue(receipt["degraded"])
        self.assertEqual(receipt["namespace_sha256"], namespace.key())
        self.assertEqual(cache.get(namespace)["status"], "MISS")

    def test_concurrent_reads_and_writes_remain_consistent(self) -> None:
        cache = ReadOnlySharedCacheAdapter(allow_write=True)
        namespace = self._namespace()
        failures: list[BaseException] = []

        def worker(index: int) -> None:
            try:
                receipt = cache.put(namespace, value={"index": index}, ttl_seconds=10, degraded=False)
                result = cache.get(namespace)
                self.assertEqual(result["status"], "HIT")
                self.assertIn("index", result["value"])
                self.assertEqual(len(receipt["response_sha256"]), 64)
            except BaseException as exc:  # pragma: no cover - reported by the parent assertion
                failures.append(exc)

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(16)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(2)
        self.assertFalse(failures)
        self.assertTrue(all(not thread.is_alive() for thread in threads))

    def test_process_shared_threads_only_adapter_reuses_across_instances(self) -> None:
        ProcessSharedCacheAdapter.reset_for_tests(); namespace=self._namespace()
        stored=ProcessSharedCacheAdapter(allow_write=True).put(namespace,value={"shared":True},ttl_seconds=5,degraded=False)
        hit=ProcessSharedCacheAdapter().get(namespace,response_sha256=stored["response_sha256"])
        self.assertEqual((hit["status"],hit["adapter_scope"],hit["value"]),("HIT","PROCESS_SHARED_THREADS_ONLY",{"shared":True}))

    def test_file_shared_shadow_adapter_reuses_across_processes_and_is_read_only_by_default(self) -> None:
        namespace = self._namespace()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); writer = FileSharedCacheAdapter(root, allow_write=True)
            stored = writer.put(namespace, value={"cross_process": True}, ttl_seconds=5, degraded=False)
            readonly = FileSharedCacheAdapter(root)
            self.assertEqual(readonly.get(namespace, response_sha256=stored["response_sha256"])["value"], {"cross_process": True})
            source_root = str(Path(__file__).resolve().parents[1] / "src")
            env = dict(os.environ); env["PYTHONPATH"] = source_root + os.pathsep + env.get("PYTHONPATH", "")
            code = "import json,sys; from llm_batch.runtime.shared_cache_contract import CacheNamespace,FileSharedCacheAdapter; n=CacheNamespace('a'*64,'publication-scope','b'*64,'provider','model','c'*64); print(json.dumps(FileSharedCacheAdapter(__import__('pathlib').Path(sys.argv[1])).get(n, response_sha256=sys.argv[2])))"
            child = subprocess.run([sys.executable, "-c", code, str(root), stored["response_sha256"]], capture_output=True, text=True, check=True, env=env)
            value = json.loads(child.stdout)
            self.assertEqual((value["status"], value["adapter_scope"], value["cache_source"]), ("HIT", "CROSS_PROCESS_FILE_SHADOW_ONLY", "CROSS_PROCESS_FILE_SHADOW"))
            self.assertEqual(readonly.put(namespace, value={"new": True}, ttl_seconds=1, degraded=False)["status"], "READ_ONLY")

    def test_file_shared_ttl_degraded_and_poison_fail_closed(self) -> None:
        namespace = self._namespace()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); cache = FileSharedCacheAdapter(root, allow_write=True)
            self.assertEqual(cache.put(namespace, value={"x": 1}, ttl_seconds=1, degraded=True)["status"], "EXCLUDED_DEGRADED")
            stored = cache.put(namespace, value={"x": 1}, ttl_seconds=.01, degraded=False)
            import time; time.sleep(.02)
            self.assertTrue(cache.get(namespace)["expired_entry_deleted"])
            cache.put(namespace, value={"x": 1}, ttl_seconds=5, degraded=False)
            path = root / f"{namespace.key()}.json"; poisoned = json.loads(path.read_text(encoding="utf-8")); poisoned["value"] = {"x": 2}; path.write_text(json.dumps(poisoned), encoding="utf-8")
            with self.assertRaisesRegex(SharedCacheContractError, "self-hash mismatch"):
                cache.get(namespace)

    def test_file_cache_expired_reader_cannot_delete_fresh_replacement(self) -> None:
        namespace = self._namespace()
        with tempfile.TemporaryDirectory() as directory:
            cache = FileSharedCacheAdapter(Path(directory), allow_write=True)
            cache.put(namespace, value={"generation": "stale"}, ttl_seconds=.01, degraded=False)
            import time; time.sleep(.02)
            delete = cache._delete_if_same_expired
            def interleaved(path, key, observed):
                cache.put(namespace, value={"generation": "fresh"}, ttl_seconds=5, degraded=False)
                return delete(path, key, observed)
            cache._delete_if_same_expired = interleaved
            missed = cache.get(namespace)
            self.assertEqual((missed["status"], missed["expired_entry_deleted"]), ("MISS", False))
            self.assertEqual(cache.get(namespace)["value"], {"generation": "fresh"})


if __name__ == "__main__":
    unittest.main()
