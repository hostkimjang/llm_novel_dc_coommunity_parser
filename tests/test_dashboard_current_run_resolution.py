"""현재 실행 결과·로그가 과거 실행으로 바뀌지 않는 대시보드 계약."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import llm_batch.monitor.server as server_module


class _State:
    def __init__(self, output_file: str = "", *, summary=None):
        self.output_file = output_file
        self.summary = summary

    def get_status(self):
        return {"output_file": self.output_file, "batch_running": True}

    def get_result_summary(self, post_id):
        return self.summary if self.summary and self.summary.get("post_id") == post_id else None

    def get_results(self, **kwargs):
        items = [dict(self.summary)] if self.summary else []
        return {"items": items, "total": len(items), "offset": 0, "limit": 200, "has_more": False}

    def get_post_logs(self, post_id):
        return []


def _result(post_id: int, title: str, confidence: str):
    return [{
        "post_id": post_id,
        "title": title,
        "analysis_result": {
            "identity": {
                "is_relevant": True,
                "novel_identity": {"official_title": title, "confidence": confidence},
            }
        },
    }]


class CurrentResultPathContract(unittest.IsolatedAsyncioTestCase):
    async def test_nested_result_json_is_authoritative_and_history_is_not_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            current = out_dir / "axis" / "actual" / "after_fresh" / "result.json"
            pending = current.with_name("result_pending_snapshot.json")
            historical = out_dir / "expert_result_20260922_210603_632991.json"
            current.parent.mkdir(parents=True)
            current.write_text(json.dumps(_result(2, "현재 제목", "Medium")), encoding="utf-8")
            pending.write_text("[]", encoding="utf-8")
            historical.write_text(json.dumps(_result(2, "과거 제목", "High")), encoding="utf-8")
            state = _State(str(current.resolve()), summary={"post_id": 2, "title": "현재 요약"})

            with (
                patch.object(server_module, "monitor", state),
                patch.object(server_module, "_OUT_DIR", out_dir),
                patch.object(server_module, "_recent_final_result_paths", return_value=[historical]),
            ):
                self.assertEqual(server_module._candidate_result_paths(), [current.resolve(), pending.resolve()])
                transport = httpx.ASGITransport(app=server_module.app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/results/2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["official_title"], "현재 제목")
        self.assertEqual(response.json()["confidence"], "Medium")

    async def test_missing_current_files_return_summary_instead_of_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            current = out_dir / "axis" / "actual" / "after_fresh" / "result.json"
            historical = out_dir / "expert_result_20260922_210603_632991.json"
            historical.parent.mkdir(parents=True)
            historical.write_text(json.dumps(_result(2, "과거 제목", "High")), encoding="utf-8")
            summary = {"post_id": 2, "title": "현재 요약", "confidence": "Medium"}
            state = _State(str(current.resolve()), summary=summary)

            with (
                patch.object(server_module, "monitor", state),
                patch.object(server_module, "_OUT_DIR", out_dir),
                patch.object(server_module, "_recent_final_result_paths", return_value=[historical]),
            ):
                transport = httpx.ASGITransport(app=server_module.app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/results/2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), summary)

    async def test_custom_json_output_under_out_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            current = out_dir / "custom" / "publication.json"
            current.parent.mkdir(parents=True)
            current.write_text(json.dumps(_result(3, "사용자 출력", "High")), encoding="utf-8")
            state = _State(str(current.resolve()), summary={"post_id": 3})
            with patch.object(server_module, "monitor", state), patch.object(server_module, "_OUT_DIR", out_dir):
                transport = httpx.ASGITransport(app=server_module.app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/results/3")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["official_title"], "사용자 출력")

    async def test_live_list_enrichment_uses_current_file_not_same_post_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            current = out_dir / "axis" / "actual" / "after_fresh" / "result.json"
            historical = out_dir / "expert_result_20260922_210603_632991.json"
            current.parent.mkdir(parents=True)
            current.write_text(json.dumps(_result(2, "현재 제목", "Medium")), encoding="utf-8")
            historical.write_text(json.dumps(_result(2, "과거 제목", "High")), encoding="utf-8")
            summary = {"post_id": 2, "title": "현재 요약"}
            with (
                patch.object(server_module, "monitor", _State(str(current.resolve()), summary=summary)),
                patch.object(server_module, "_OUT_DIR", out_dir),
                patch.object(server_module, "_recent_final_result_paths", return_value=[historical]),
            ):
                transport = httpx.ASGITransport(app=server_module.app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/results")
        payload = response.json()
        self.assertEqual(payload["items"][0]["official_title"], "현재 제목")
        self.assertEqual(payload["items"][0]["confidence"], "Medium")

    def test_unsafe_or_non_json_current_binding_never_falls_back_to_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "repo" / "out"
            history = out_dir / "expert_result_20260922_210603_632991.json"
            history.parent.mkdir(parents=True)
            history.write_text("[]", encoding="utf-8")
            for declared in (root / "outside.json", out_dir / "actual" / "result.jsonl"):
                with self.subTest(declared=declared):
                    with (
                        patch.object(server_module, "monitor", _State(str(declared.resolve()))),
                        patch.object(server_module, "_OUT_DIR", out_dir),
                        patch.object(server_module, "_recent_final_result_paths", return_value=[history]),
                    ):
                        self.assertEqual(server_module._candidate_result_paths(), [])

    def test_no_current_output_keeps_legacy_history_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            history = out_dir / "expert_result_20260922_210603_632991.json"
            with (
                patch.object(server_module, "monitor", _State()),
                patch.object(server_module, "_OUT_DIR", out_dir),
                patch.object(server_module, "_recent_final_result_paths", return_value=[history]),
            ):
                self.assertEqual(server_module._candidate_result_paths(), [history])


class CurrentLogBindingContract(unittest.IsolatedAsyncioTestCase):
    async def test_history_run_uses_full_run_id_log_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "out"
            log_dir = root / "logs"
            out_dir.mkdir()
            log_dir.mkdir()
            result = out_dir / "expert_result_20260922_234704_270181.json"
            current_named = out_dir / "result.json"
            log = log_dir / "expert_run_20260922_234704_270181.log"
            result.write_text("[]", encoding="utf-8")
            current_named.write_text("[]", encoding="utf-8")
            log.write_text("ok", encoding="utf-8")
            with (
                patch.object(server_module, "_OUT_DIR", out_dir),
                patch.object(server_module, "_LOG_DIR", log_dir),
            ):
                response = await server_module.api_runs()
        payload = json.loads(response.body)
        self.assertEqual([item["filename"] for item in payload], [result.name])
        self.assertEqual(payload[0]["log_file"], log.name)

    async def test_post_log_is_limited_to_current_run_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "out"
            log_dir = root / "logs"
            current_dir = out_dir / "axis" / "actual" / "after_fresh"
            current_dir.mkdir(parents=True)
            log_dir.mkdir()
            current = current_dir / "result.json"
            current.write_text("[]", encoding="utf-8")
            (current_dir / "result_manifest.json").write_text(
                json.dumps({
                    "run_id": "20260922_234704_270181",
                    "output_file": str(current.resolve()),
                }),
                encoding="utf-8",
            )
            current_log = log_dir / "expert_run_20260922_234704_270181_W2.log"
            old_log = log_dir / "expert_run_20260922_210603_632991_W2.log"
            current_log.write_text(
                "==========\n📌 Post ID: 2\nCURRENT\n✅ Post 2 완료\n", encoding="utf-8"
            )
            old_log.write_text(
                "==========\n📌 Post ID: 2\nOLD\n✅ Post 2 완료\n", encoding="utf-8"
            )
            with (
                patch.object(server_module, "monitor", _State(str(current.resolve()))),
                patch.object(server_module, "_OUT_DIR", out_dir),
                patch.object(server_module, "_LOG_DIR", log_dir),
            ):
                response = server_module.api_post_log(2, source="file")
        payload = json.loads(response.body)
        self.assertIn("CURRENT", payload["lines"])
        self.assertNotIn("OLD", payload["lines"])
        self.assertEqual(payload["source"], current_log.name)

    async def test_mismatched_manifest_cannot_select_a_current_run_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "out"
            log_dir = root / "logs"
            current_dir = out_dir / "axis" / "actual" / "after_fresh"
            current_dir.mkdir(parents=True)
            log_dir.mkdir()
            current = current_dir / "result.json"
            current.write_text("[]", encoding="utf-8")
            (current_dir / "result_manifest.json").write_text(
                json.dumps({
                    "run_id": "20260922_234704_270181",
                    "output_file": str((current_dir / "other.json").resolve()),
                }),
                encoding="utf-8",
            )
            old_log = log_dir / "expert_run_20260922_210603_632991_W2.log"
            old_log.write_text(
                "==========\n📌 Post ID: 2\nOLD\n✅ Post 2 완료\n", encoding="utf-8"
            )
            with (
                patch.object(server_module, "monitor", _State(str(current.resolve()))),
                patch.object(server_module, "_OUT_DIR", out_dir),
                patch.object(server_module, "_LOG_DIR", log_dir),
            ):
                response = server_module.api_post_log(2, source="file")
        self.assertEqual(response.status_code, 404)
        payload = json.loads(response.body)
        self.assertEqual(payload["lines"], [])


if __name__ == "__main__":
    unittest.main()
