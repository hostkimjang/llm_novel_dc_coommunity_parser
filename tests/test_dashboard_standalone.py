"""standalone 대시보드 분리(ingest/forwarder/감지) 동작 검증."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm_batch.monitor.event_bus import MonitorState
from llm_batch.monitor.forwarder import DashboardForwarder
import llm_batch.monitor.server as server_module
import expert_main as expert_main_module


STATIC_INDEX = Path(__file__).resolve().parents[1] / "src" / "llm_batch" / "monitor" / "static" / "index.html"


def _call_ingest(payload, headers=None):
    request = SimpleNamespace(headers=headers or {})
    response = server_module.api_ingest(request, payload)
    return response.status_code, json.loads(response.body)


class DashboardStaticUiContractTest(unittest.TestCase):
    def test_semantics_readback_keeps_row_capture_and_manifest_policy_separate(self):
        from llm_batch.monitor.run_index import row_meta, summary
        row = {
            "candidate_reranker_semantics": {
                "status": "NOT_EXECUTED", "observation": None,
                "consumption": {"scorer_input_applied": False, "calibration_input_applied": False},
            },
            "candidate_reranker_semantics_capture": {
                "status": "NOT_AVAILABLE", "artifact": None, "publication_authority": False,
            },
        }
        policy = {"candidate_reranker_semantics_policy": {
            "mode": "SHADOW", "actual_quality_evaluated": False,
        }}
        self.assertEqual(row_meta({"run_meta": {**row, **policy, "other": "private"}}), row)
        self.assertEqual(summary({**policy, **row, "other": "private"}), policy)

    def test_semantics_known_run_and_scope_conflicts_hide_manifest_without_reading_capture(self):
        from llm_batch.monitor.run_index import bound_manifest
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "result.json"
            payload = {"output_file": str(output), "run_id": "run-current",
                       "publication_scope_id": "scope-current",
                       "candidate_reranker_semantics_policy": {"mode": "SHADOW"}}
            coordinates = {"run_id": "run-current", "publication_scope_id": "scope-current"}
            meta = {**coordinates, "candidate_reranker_semantics": {
                "status": "OBSERVED", "binding": dict(coordinates)},
                "candidate_reranker_semantics_capture": {
                    "status": "SAVED", "binding": dict(coordinates),
                    "artifact": {"path": "outside-must-not-read.json", "sha256": "f" * 64, "bytes": 0}}}
            with (patch.object(Path, "read_text", side_effect=AssertionError("artifact read")),
                  patch.object(Path, "read_bytes", side_effect=AssertionError("artifact read"))):
                result = bound_manifest(output, root, item={"run_meta": meta}, payload=payload)
                self.assertEqual(result["binding_status"], "BOUND")
                self.assertEqual(result["summary"]["candidate_reranker_semantics_policy"], {"mode": "SHADOW"})
                for name in ("candidate_reranker_semantics", "candidate_reranker_semantics_capture"):
                    for key, reason in (("run_id", "RUN_ID"), ("publication_scope_id", "PUBLICATION_SCOPE")):
                        for nested in (False, True):
                            with self.subTest(name=name, key=key, nested=nested):
                                changed = json.loads(json.dumps(meta))
                                target = changed[name]["binding"] if nested else changed[name]
                                target[key] = "other-execution"
                                mismatch = bound_manifest(output, root, item={"run_meta": changed}, payload=payload)
                                self.assertEqual(mismatch["binding_status"], "MISMATCH")
                                self.assertIn(reason + "_ROW_CONFLICT", mismatch["reason_codes"])
                                self.assertEqual(mismatch["summary"], {})
                partial = bound_manifest(output, root, item={"run_meta": {
                    "candidate_reranker_semantics": {"binding": {"run_id": "run-current"}}}}, payload=payload)
                self.assertEqual(partial["binding_status"], "PARTIAL")
                self.assertIn("PUBLICATION_SCOPE_NOT_RECORDED", partial["reason_codes"])

    def test_paired_observations_keep_row_and_run_provenance_in_readback(self):
        from llm_batch.monitor.run_index import row_meta, summary
        row = {"paired_execution_observation": {"start": {"binding": {"attempt_id": "row"}}, "end": None},
               "paired_execution_runtime_fields": {"mutable_context_mode": "FROZEN_OFF"}}
        run = {"paired_execution_observation": {"start": {"binding": {"attempt_id": "run"}}, "end": None},
               "paired_execution_runtime_fields": {"mutable_context_mode": "FROZEN_OFF"}}
        self.assertEqual(row_meta({"run_meta": {**row, "unrelated": "private"}}), row)
        self.assertEqual(summary({**run, "unrelated": "private"}), run)
        self.assertNotEqual(row_meta({"run_meta": row}), summary(run))

    def test_live_filter_reload_uses_latest_request_and_restore_guard(self):
        html = STATIC_INDEX.read_text(encoding="utf-8")
        self.assertIn("let _livePendingReloadPage = null;", html)
        self.assertIn("if (livePageLoading) {\n    _livePendingReloadPage = Math.max(page, 0);", html)
        self.assertIn("const nextPage = _livePendingReloadPage;", html)
        self.assertIn("loadLiveResults(nextPage);", html)
        self.assertIn("if (liveFilterActive()) return;  // 필터 스냅샷 보호: restore/gap 재조회도 일시정지", html)

    def test_static_assets_use_dashboard_release_version(self):
        html = STATIC_INDEX.read_text(encoding="utf-8")
        version = "20260922-reason-log-v1"
        for name in ("theme.js", "presentation.js", "utilities.css", "dashboard.css"):
            with self.subTest(name=name):
                asset_version = "20261012-nsfw-assessment-v1" if name == "presentation.js" else version
                self.assertIn(f"/static/{name}?v={asset_version}", html)

    def test_modal_json_copy_sanitizes_internal_warning_and_has_fallback(self):
        html = STATIC_INDEX.read_text(encoding="utf-8")
        self.assertIn("const { _detail_warning, ...payload } = _modalCurrentData;", html)
        self.assertIn("navigator.clipboard && navigator.clipboard.writeText", html)
        self.assertIn("document.execCommand('copy')", html)


class DashboardStaticAssetTest(unittest.IsolatedAsyncioTestCase):
    async def test_dashboard_css_and_javascript_are_served_with_correct_types(self):
        transport = httpx.ASGITransport(app=server_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://dashboard.test") as client:
            for name, content_type in (
                ("dashboard.css", "text/css"),
                ("utilities.css", "text/css"),
                ("theme.js", "javascript"),
                ("presentation.js", "javascript"),
            ):
                with self.subTest(asset=name):
                    asset = STATIC_INDEX.parent / name
                    self.assertTrue(asset.is_file(), f"대시보드 자산 누락: {name}")
                    response = await client.get(f"/static/{name}")
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(content_type, response.headers["content-type"])
                    self.assertEqual(response.content, asset.read_bytes())

    async def test_missing_asset_and_files_outside_static_directory_are_not_served(self):
        transport = httpx.ASGITransport(app=server_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://dashboard.test") as client:
            for path in ("/static/missing-dashboard-asset.css", "/static/server.py"):
                with self.subTest(path=path):
                    response = await client.get(path)
                self.assertEqual(response.status_code, 404)


class DashboardResultPathBindingTest(unittest.TestCase):
    def test_current_nested_absolute_result_and_sibling_snapshot_are_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            result_path = out_dir / "actual" / "expert_result_20260922_163120_592728.json"
            pending_path = result_path.with_name(
                "expert_result_20260922_163120_592728_pending_snapshot.json"
            )
            result_path.parent.mkdir(parents=True)
            result_path.write_text("[]\n", encoding="utf-8")
            pending_path.write_text("[]\n", encoding="utf-8")

            state = MonitorState()
            state.output_file = str(result_path.resolve())
            with (
                patch.object(server_module, "monitor", state),
                patch.object(server_module, "_OUT_DIR", out_dir),
                patch.object(server_module, "_recent_final_result_paths", return_value=[]),
            ):
                candidates = server_module._candidate_result_paths()

        self.assertEqual(candidates[:2], [result_path.resolve(), pending_path.resolve()])

    def test_absolute_result_outside_repository_out_is_not_exposed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "repo" / "out"
            outside = root / "private" / "expert_result_20260922_163120_592728.json"
            outside.parent.mkdir(parents=True)
            outside.write_text('[{"post_id": 1}]\n', encoding="utf-8")
            state = MonitorState()
            state.output_file = str(outside.resolve())
            with (
                patch.object(server_module, "monitor", state),
                patch.object(server_module, "_OUT_DIR", out_dir),
                patch.object(server_module, "_recent_final_result_paths", return_value=[]),
            ):
                self.assertEqual(server_module._candidate_result_paths(), [])

    def test_legacy_basename_still_resolves_under_repository_out(self):
        output_name = "expert_result_20260922_144656_261353.json"
        state = MonitorState()
        state.output_file = output_name
        with (
            patch.object(server_module, "monitor", state),
            patch.object(server_module, "_recent_final_result_paths", return_value=[]),
        ):
            candidates = server_module._candidate_result_paths()

        output_path = server_module._OUT_DIR / output_name
        self.assertEqual(
            candidates,
            [
                output_path,
                output_path.with_name(
                    "expert_result_20260922_144656_261353_pending_snapshot.json"
                ),
            ],
        )

    def test_expert_main_emits_resolved_result_path(self):
        source = Path(expert_main_module.__file__).read_text(encoding="utf-8")
        self.assertIn('"output_file": str(out_result_path.resolve())', source)


class DashboardResultSummaryFallbackTest(unittest.IsolatedAsyncioTestCase):
    async def test_nsfw_assessment_live_history_api_preserves_status_value_and_legacy(self):
        from llm_batch.monitor.run_index import RunIndex
        # 실제 파일/API 경계의 합성 자료다. 생산자 재실행이나 픽셀 판정 fixture가 아니다.
        analyses = [
            {"notes": "미평가", "is_nsfw": False, "nsfw_assessment_status": "NOT_EVALUATED"},
            {"notes": "모델 보고", "is_nsfw": False, "nsfw_assessment_status": "MODEL_REPORTED"},
            {"notes": "원문 규칙", "is_nsfw": True, "nsfw_assessment_status": "SOURCE_RULE_POSITIVE"},
            {"notes": "과거 null", "is_nsfw": False, "nsfw_assessment_status": None},
            {"notes": "과거 키 없음", "is_nsfw": False},
        ]
        rows = [{"post_id": 9000 + index, "title": "내용 평가 상태",
                 "analysis_result": {"identity": {"is_relevant": False}, "analysis": analysis},
                 "run_meta": {"run_id": "20261012_010203_040506",
                              "decision_call_ledger": {"publication_scope_id": "assessment-synthetic"}}}
                for index, analysis in enumerate(analyses)]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            path = out / "assessment" / "result.json"
            path.parent.mkdir()
            path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            manifest = path.with_name("result_manifest.json")
            manifest.write_text(json.dumps({"output_file": str(path),
                "run_id": "20261012_010203_040506", "publication_scope_id": "assessment-synthetic"}), encoding="utf-8")
            before = (path.read_bytes(), manifest.read_bytes())
            state = MonitorState()
            state.output_file = str(path.resolve())
            with (patch.object(server_module, "monitor", state),
                  patch.object(server_module, "_OUT_DIR", out),
                  patch.object(server_module, "_run_index", RunIndex())):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server_module.app),
                                             base_url="http://dashboard.test") as client:
                    runs = await client.get("/api/runs")
                    self.assertEqual(runs.status_code, 200)
                    self.assertEqual(len(runs.json()), 1)
                    key = runs.json()[0]["run_key"]
                    for row in rows:
                        with self.subTest(post_id=row["post_id"]):
                            live = await client.get(f"/api/results/{row['post_id']}")
                            history = await client.get(f"/api/runs/{key}/posts/{row['post_id']}")
                            self.assertEqual((live.status_code, history.status_code), (200, 200))
                            expected = row["analysis_result"]["analysis"]
                            self.assertEqual(live.json()["analysis"], expected)
                            self.assertEqual(history.json()["analysis_result"]["analysis"], expected)
                            self.assertEqual(live.json()["run_manifest"]["binding_status"], "BOUND")
                            self.assertEqual(history.json()["run_manifest"]["binding_status"], "BOUND")
            self.assertEqual(before, (path.read_bytes(), manifest.read_bytes()))

    async def test_detail_returns_current_summary_when_bound_files_have_no_post(self):
        state = MonitorState()
        state.ingest_event(
            "post_complete",
            {"post_id": 11718099, "title": "현재 run 요약", "is_relevant": False},
        )
        transport = httpx.ASGITransport(app=server_module.app)
        with (
            patch.object(server_module, "monitor", state),
            patch.object(server_module, "_candidate_result_paths", return_value=[]),
        ):
            async with httpx.AsyncClient(
                transport=transport, base_url="http://dashboard.test"
            ) as client:
                response = await client.get("/api/results/11718099")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "현재 run 요약")


class MonitorIngestTest(unittest.TestCase):
    def test_ingest_keeps_current_scope_in_summary_without_heavy_diagnostics(self):
        state = MonitorState()
        state.ingest_event("post_complete", {
            "post_id": 15, "worker_id": 0, "is_relevant": True,
            "identity_state": "unresolved_title",
            "is_novel_related": True, "is_resolved_work_discussion": False,
            "title_resolution_state": "unresolved_matchable",
            "title_resolution_allowed": False,
            "primary_subject_text": "작품 제목은 미확정입니다.",
            "candidate_ledger": {"large": [1] * 1000},
        })
        summary = state.get_result_summary(15)
        self.assertTrue(summary["is_novel_related"])
        self.assertFalse(summary["title_resolution_allowed"])
        self.assertFalse(summary["is_resolved_work_discussion"])
        self.assertEqual(summary["identity_state"], "unresolved_title")
        self.assertNotIn("candidate_ledger", summary)

    def test_legacy_summary_is_enriched_with_current_scope_fields(self):
        identity = {
            "is_relevant": True,
            "identity_state": "unresolved_title",
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_state": "unresolved_matchable",
            "title_resolution_allowed": False,
            "primary_subject_type": "work",
            "primary_subject_text": "작품 제목은 미확정입니다.",
            "topicality": "specific_work",
            "subtype": "discussion",
            "work_resolution": "unresolved",
            "reason": "근거 부족",
        }
        summary = {
            "post_id": 12,
            "topicality": "specific_work",
            "subtype": "discussion",
            "work_resolution": "unresolved",
            "reason": "근거 부족",
        }
        self.assertTrue(server_module._summary_needs_identity_enrichment(summary))
        enriched = server_module._enrich_summary_from_result(
            summary,
            {"post_id": 12, "analysis_result": {"identity": identity}},
        )
        self.assertFalse(enriched["title_resolution_allowed"])
        self.assertEqual(enriched["identity_state"], "unresolved_title")
        self.assertEqual(enriched["primary_subject_type"], "work")

    def test_live_detail_preserves_current_identity_contract_without_changing_input(self):
        identity = {
            "is_relevant": True,
            "is_novel_related": True,
            "is_resolved_work_discussion": False,
            "title_resolution_state": "unresolved_matchable",
            "title_resolution_allowed": False,
            "search_health": {"accepted": 0, "status": "SEARCH_DEGRADED"},
            "image_evidence_catalog": [{"eid": "IMG001", "ocr_text": "표지의 제목 후보"}],
            "candidate_ledger_status": "UNKNOWN",
            "future_contract_field": {"state": False},
        }
        item = {"post_id": 12, "title": "화면 검증", "analysis_result": {"identity": identity}}
        before = json.dumps(item, ensure_ascii=False)
        detail = server_module._to_live_detail(item, summary={"elapsed": 1.5})
        for key, value in identity.items():
            self.assertEqual(detail[key], value)
        self.assertEqual(detail["post_id"], 12)
        self.assertEqual(detail["elapsed"], 1.5)
        self.assertEqual(json.dumps(item, ensure_ascii=False), before)

    def test_ingest_event_updates_state_and_batch_start_resets(self):
        state = MonitorState()
        state.ingest_event("batch_start", {"total": 5, "parallel_count": 2})
        self.assertTrue(state.batch_running)
        self.assertEqual(state.total_posts, 5)

        state.ingest_event("post_start", {"post_id": 11, "index": 1, "title": "t", "worker_id": 0})
        state.ingest_event(
            "post_complete",
            {"post_id": 11, "title": "t", "is_relevant": True, "worker_id": 0,
             "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
        )
        self.assertEqual(len(state.post_summaries), 1)
        self.assertEqual(state.token_usage["total_tokens"], 15)

        # 다음 런의 batch_start가 상태를 리셋한다 (연속 런 지원의 핵심)
        state.ingest_event("batch_start", {"total": 3})
        self.assertEqual(state.total_posts, 3)
        self.assertEqual(state.post_summaries, [])
        self.assertEqual(state.token_usage["total_tokens"], 0)

    def test_load_status_snapshot_overwrites_counters(self):
        state = MonitorState()
        state.ingest_event("batch_start", {"total": 10})
        state.load_status_snapshot({
            "batch_running": True,
            "total_posts": 10,
            "token_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "search_hits": 7,
            "search_misses": 2,
            "post_summaries": [{"post_id": 1}, {"post_id": 2}],
            "batch_start_time": 12345.0,
        })
        self.assertEqual(state.token_usage["total_tokens"], 150)
        self.assertEqual(state.search_hits, 7)
        self.assertEqual(len(state.post_summaries), 2)
        self.assertEqual(state.batch_start_time, 12345.0)

        # 로컬에 더 많은 요약이 있으면 스냅샷(최근 500건 제한)으로 줄이지 않는다
        state.post_summaries = [{"post_id": i} for i in range(5)]
        state.load_status_snapshot({"post_summaries": [{"post_id": 9}]})
        self.assertEqual(len(state.post_summaries), 5)

    def test_emit_and_add_log_enqueue_to_forwarder(self):
        state = MonitorState()
        captured = []
        state.attach_forwarder(SimpleNamespace(enqueue=captured.append))

        state.emit("post_start", {"post_id": 1, "worker_id": 0})
        self.assertEqual(captured[-1]["kind"], "event")
        self.assertEqual(captured[-1]["type"], "post_start")

        state.add_log("hello", worker_id=0)
        self.assertEqual(captured[-1]["kind"], "log")

        # SSE skip 태그는 포워딩에서도 제외된다 (같은 필터 상속)
        before = len(captured)
        state.add_log("[llm-debug] verbose", worker_id=0)
        self.assertEqual(len(captured), before)

    def test_ingest_event_does_not_reforward(self):
        state = MonitorState()
        captured = []
        state.attach_forwarder(SimpleNamespace(enqueue=captured.append))
        state.ingest_event("post_start", {"post_id": 1})
        self.assertEqual(captured, [])

    def test_post_complete_dedupe_prevents_double_counting(self):
        # forwarder at-least-once 재전송/스냅샷+백로그 중복으로 같은 post_complete가
        # 두 번 들어와도 카운터/토큰이 이중 가산되지 않는다
        state = MonitorState()
        state.ingest_event("batch_start", {"total": 2})
        event = {"post_id": 5, "title": "t", "is_relevant": True,
                 "token_usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
        state.ingest_event("post_complete", dict(event))
        state.ingest_event("post_complete", dict(event))
        self.assertEqual(state.done_count, 1)
        self.assertEqual(len(state.post_summaries), 1)
        self.assertEqual(state.token_usage["total_tokens"], 2)
        self.assertEqual(state.get_status()["done_count"], 1)

    def test_done_count_survives_500_cap_resync(self):
        # 대시보드 재시작 리싱크: 요약은 500건 캡이어도 진행률은 카운터로 유지
        state = MonitorState()
        state.ingest_event("batch_start", {"total": 104502})
        state.load_status_snapshot({
            "batch_running": True,
            "total_posts": 104502,
            "done_count": 50000,
            "relevant_count": 30000,
            "noise_count": 20000,
            "post_summaries": [{"post_id": i} for i in range(500)],
        })
        status = state.get_status()
        self.assertEqual(status["done_count"], 50000)
        self.assertEqual(status["relevant_count"], 30000)
        self.assertEqual(len(state.post_summaries), 500)

    def test_post_log_keeps_collecting_after_post_complete(self):
        # 완료 직후 출력되는 요약/토큰 라인도 포스트 처리 로그에 수집되어야
        # "처리 로그 끝이 잘리는" 문제가 없다 (다음 post_start가 매핑을 교체)
        state = MonitorState()
        state.emit("batch_start", {"total": 2, "parallel_count": 2})
        state.emit("post_start", {"post_id": 1, "worker_id": 0})
        state.add_log("처리 중 라인", worker_id=0)
        state.emit("post_complete", {"post_id": 1, "worker_id": 0})
        state.add_log("✅ Post 1 완료 요약 라인", worker_id=0)
        self.assertIn("✅ Post 1 완료 요약 라인", state.get_post_logs(1))
        # 같은 워커의 다음 포스트가 시작되면 라우팅이 넘어간다
        state.emit("post_start", {"post_id": 2, "worker_id": 0})
        state.add_log("다음 포스트 라인", worker_id=0)
        self.assertNotIn("다음 포스트 라인", state.get_post_logs(1))
        self.assertIn("다음 포스트 라인", state.get_post_logs(2))

    def test_active_post_flow_log_capped(self):
        state = MonitorState()
        state.emit("batch_start", {"total": 1, "parallel_count": 2})
        state.emit("post_start", {"post_id": 1, "worker_id": 0})
        for i in range(50):
            state.emit("expert_phase", {"expert": f"e{i}", "status": "running", "post_id": 1})
        self.assertEqual(len(state.active_posts[1]["flow_log"]), 30)
        self.assertEqual(state.active_posts[1]["flow_log"][-1]["expert"], "e49")

    def test_sse_post_complete_broadcast_drops_heavy_fields(self):
        # 슬림화는 _broadcast 내부에서 일어나므로 직렬화 직전(json.dumps)에서 캡처
        import llm_batch.monitor.event_bus as event_bus_module

        state = MonitorState()
        captured = {}
        real_dumps = json.dumps

        def _spy_dumps(obj, **kwargs):
            if isinstance(obj, dict) and obj.get("type") == "post_complete":
                captured.update(obj)
            return real_dumps(obj, **kwargs)

        with patch.object(event_bus_module.json, "dumps", _spy_dumps):
            state.emit("post_complete", {
                "post_id": 1,
                "title": "t",
                "is_relevant": True,
                "reason": "긴 판정 사유 " * 100,
                "reason_lines": ["a"] * 50,
                "analysis_notes": "노트",
                "official_title": "공식 제목",
            })
        data = captured.get("data") or {}
        self.assertNotIn("reason", data)
        self.assertNotIn("reason_lines", data)
        self.assertNotIn("analysis_notes", data)
        # 행 렌더에 필요한 필드는 유지
        self.assertEqual(data.get("official_title"), "공식 제목")
        # 저장본(post_summaries)에는 reason이 그대로 남는다
        self.assertEqual(state.post_summaries[0].get("analysis_notes"), "노트")

    def test_get_results_search_and_relevance_filter(self):
        state = MonitorState()
        state.ingest_event("batch_start", {"total": 4})
        state.ingest_event("post_complete", {"post_id": 1, "title": "전독시 토론", "official_title": "전지적 독자 시점", "is_relevant": True})
        state.ingest_event("post_complete", {"post_id": 2, "title": "잡담", "is_relevant": False})
        state.ingest_event("post_complete", {"post_id": 3, "title": "화산귀환 후기", "official_title": "화산귀환", "is_relevant": True})

        # relevance 필터
        relevant = state.get_results(relevance="relevant")
        self.assertEqual([it["post_id"] for it in relevant["items"]], [3, 1])
        self.assertEqual(relevant["total"], 2)
        noise = state.get_results(relevance="noise")
        self.assertEqual([it["post_id"] for it in noise["items"]], [2])

        # q 검색: 제목/공식제목/post_id 부분일치, 대소문자 무시
        self.assertEqual([it["post_id"] for it in state.get_results(q="독자")["items"]], [1])
        self.assertEqual([it["post_id"] for it in state.get_results(q="화산")["items"]], [3])
        self.assertEqual([it["post_id"] for it in state.get_results(q="2")["items"]], [2])
        # 검색+필터 결합
        combo = state.get_results(q="전독시", relevance="noise")
        self.assertEqual(combo["items"], [])
        # 기본 호출은 기존 동작 그대로
        all_items = state.get_results()
        self.assertEqual(all_items["total"], 3)

    def test_parallel_mode_does_not_accumulate_sequential_flow_log(self):
        state = MonitorState()
        state.ingest_event("batch_start", {"total": 10, "parallel_count": 32})
        state.ingest_event("post_start", {"post_id": 1, "worker_id": 0})
        state.ingest_event("expert_phase", {"expert": "gatekeeper", "status": "running", "post_id": 1})
        self.assertEqual(state._flow_log, [])
        # 순차 모드에서는 기존대로 누적
        state.ingest_event("batch_start", {"total": 1, "parallel_count": 1})
        state.ingest_event("post_start", {"post_id": 2, "worker_id": 0})
        state.ingest_event("expert_phase", {"expert": "gatekeeper", "status": "running", "post_id": 2})
        self.assertEqual(len(state._flow_log), 1)


class ServerIngestEndpointTest(unittest.TestCase):
    def setUp(self):
        self._fresh = MonitorState()
        self._patcher = patch.object(server_module, "monitor", self._fresh)
        self._patcher.start()
        # ingest는 standalone 모드 전용 — 내장 모드 프로세스로의 교차 주입 차단
        self._env_patcher = patch.dict(os.environ, {"DASHBOARD_STANDALONE": "1"})
        self._env_patcher.start()

    def tearDown(self):
        self._env_patcher.stop()
        self._patcher.stop()

    def test_ingest_rejected_in_embedded_mode(self):
        with patch.dict(os.environ, {"DASHBOARD_STANDALONE": "0"}):
            status, body = _call_ingest({"items": []})
        self.assertEqual(status, 403)
        self.assertIn("standalone", body["error"])

    def test_ingest_batch_accepts_events_and_logs(self):
        status, body = _call_ingest({
            "items": [
                {"kind": "event", "type": "batch_start", "data": {"total": 2}},
                {"kind": "log", "line": "line-1", "worker_id": 0},
                {"kind": "status_snapshot", "data": {"search_hits": 3}},
                {"kind": "unknown"},
            ]
        })
        self.assertEqual(status, 200)
        self.assertEqual(body["received"], 4)
        self.assertEqual(body["accepted"], 3)
        self.assertEqual(self._fresh.total_posts, 2)
        self.assertEqual(self._fresh.search_hits, 3)
        # worker_id=0이 -1(메인)로 오귀속되지 않아야 한다 (`0 or -1` 회귀 방지)
        self.assertEqual(self._fresh._worker_log_lines.get(0), ["line-1"])

    def test_ingest_log_broadcasts_every_line_without_throttle(self):
        # 발신 측이 이미 50ms 쓰로틀을 적용했으므로 수신 측은 전부 SSE 브로드캐스트
        broadcasts = []
        with patch.object(self._fresh, "_broadcast", side_effect=broadcasts.append):
            _call_ingest({
                "items": [
                    {"kind": "log", "line": f"l{i}", "worker_id": -1} for i in range(10)
                ]
            })
        log_broadcasts = [b for b in broadcasts if b.get("type") == "log"]
        self.assertEqual(len(log_broadcasts), 10)

    def test_resume_chain_survives_dashboard_restart_via_snapshot(self):
        # suspend 도중 대시보드가 재시작 → 스냅샷 리싱크로 suspend 상태 복원
        source = MonitorState()
        source.emit("llm_suspend", {"failure_count": 3, "threshold": 3, "message": "down"})
        snapshot = source.get_status()
        _call_ingest({"items": [{"kind": "status_snapshot", "data": snapshot}]})
        self.assertTrue(self._fresh.llm_suspended)

    def test_ingest_token_enforced_when_configured(self):
        with patch.dict(os.environ, {"DASHBOARD_INGEST_TOKEN": "secret"}):
            status, _body = _call_ingest({"items": []})
            self.assertEqual(status, 403)
            status, body = _call_ingest({"items": []}, headers={"X-Ingest-Token": "secret"})
            self.assertEqual(status, 200)
            self.assertFalse(body["resume_requested"])

    def test_resume_piggyback_flag_returned_once(self):
        with server_module._pending_resume_lock:
            server_module._pending_resume_requested = True
        _status, body = _call_ingest({"items": []})
        self.assertTrue(body["resume_requested"])
        _status, body = _call_ingest({"items": []})
        self.assertFalse(body["resume_requested"])


class ForwarderQueueTest(unittest.TestCase):
    def test_native_completion_is_critical_and_retry_preserved_without_starting_http(self):
        fwd = self._make()
        fwd.enqueue({"kind": "event", "type": "native_recovery_progress", "data": {"sequence": 1}})
        fwd.enqueue({"kind": "event", "type": "native_recovery_complete", "data": {"sequence": 2}})
        self.assertEqual(len(fwd._critical), 1)
        batch = fwd._drain_batch()
        fwd._requeue_critical(batch)
        self.assertEqual(len(fwd._critical), 1)
        self.assertEqual(fwd._critical[0]["type"], "native_recovery_complete")

    def _make(self, **kwargs):
        return DashboardForwarder("http://127.0.0.1:9", **kwargs)

    def test_enqueue_classifies_critical_and_bulk(self):
        fwd = self._make()
        fwd.enqueue({"kind": "event", "type": "post_complete", "data": {}})
        fwd.enqueue({"kind": "event", "type": "expert_phase", "data": {}})
        fwd.enqueue({"kind": "log", "line": "x", "worker_id": -1})
        self.assertEqual(len(fwd._critical), 1)
        self.assertEqual(len(fwd._bulk), 2)

    def test_bulk_overflow_drops_oldest_and_reports(self):
        fwd = self._make(bulk_maxlen=2)
        for i in range(4):
            fwd.enqueue({"kind": "log", "line": f"l{i}", "worker_id": -1})
        batch = fwd._drain_batch()
        # 2건 유지 + 드롭 보고 로그 1건
        self.assertEqual(len(batch), 3)
        self.assertIn("드롭", batch[-1]["line"])

    def test_drain_batch_restores_enqueue_order_across_queues(self):
        # critical-우선 '보존'은 유지하되 전송 순서는 발행 순서를 따라야 한다
        fwd = self._make()
        fwd.enqueue({"kind": "event", "type": "expert_phase", "data": {"n": 1}})
        fwd.enqueue({"kind": "event", "type": "post_complete", "data": {"n": 2}})
        fwd.enqueue({"kind": "log", "line": "after", "worker_id": -1})
        batch = fwd._drain_batch()
        kinds = [(i.get("type") or i.get("kind")) for i in batch]
        self.assertEqual(kinds, ["expert_phase", "post_complete", "log"])

    def test_requeue_critical_preserves_order_and_skips_bulk(self):
        fwd = self._make()
        batch = [
            {"kind": "event", "type": "post_start", "data": {"i": 1}},
            {"kind": "log", "line": "x", "worker_id": -1},
            {"kind": "event", "type": "post_complete", "data": {"i": 2}},
        ]
        fwd._requeue_critical(batch)
        self.assertEqual(len(fwd._critical), 2)
        self.assertEqual(fwd._critical[0]["type"], "post_start")
        self.assertEqual(fwd._critical[1]["type"], "post_complete")

    def test_flush_and_stop_posts_remaining_critical(self):
        fwd = self._make()
        fwd.enqueue({"kind": "event", "type": "batch_complete", "data": {"total": 1}})
        posted = []
        with patch.object(fwd, "_post_items", side_effect=lambda items: posted.extend(items) or {}):
            fwd.flush_and_stop(timeout=1.0)
        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0]["type"], "batch_complete")
        # 종료 후 enqueue는 무시된다
        fwd.enqueue({"kind": "event", "type": "post_start", "data": {}})
        self.assertEqual(len(fwd._critical), 0)


class DetectExternalDashboardTest(unittest.TestCase):
    def _resp(self, payload):
        return SimpleNamespace(json=lambda: payload)

    def test_detects_standalone_only(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DASHBOARD_URL", None)
            os.environ.pop("EXPERT_DASHBOARD_FORWARD", None)
            with patch("httpx.get", return_value=self._resp(
                {"ok": True, "service": "expert-pipeline-monitor", "standalone": True}
            )):
                self.assertEqual(
                    expert_main_module._detect_external_dashboard(8080),
                    "http://127.0.0.1:8080",
                )
            # 내장 대시보드(standalone=False)에는 양보하지 않는다
            with patch("httpx.get", return_value=self._resp(
                {"ok": True, "service": "expert-pipeline-monitor", "standalone": False}
            )):
                self.assertIsNone(expert_main_module._detect_external_dashboard(8080))
            # 무관한 앱
            with patch("httpx.get", return_value=self._resp({"hello": "world"})):
                self.assertIsNone(expert_main_module._detect_external_dashboard(8080))
            # 연결 실패
            with patch("httpx.get", side_effect=ConnectionError("refused")):
                self.assertIsNone(expert_main_module._detect_external_dashboard(8080))

    def test_forward_opt_out_and_url_override(self):
        with patch.dict(os.environ, {"EXPERT_DASHBOARD_FORWARD": "0"}):
            self.assertIsNone(expert_main_module._detect_external_dashboard(8080))
        with patch.dict(os.environ, {"DASHBOARD_URL": "http://127.0.0.1:9999/"}):
            os.environ.pop("EXPERT_DASHBOARD_FORWARD", None)
            with patch("httpx.get", return_value=self._resp(
                {"ok": True, "service": "expert-pipeline-monitor", "standalone": True}
            )) as mock_get:
                self.assertEqual(
                    expert_main_module._detect_external_dashboard(8080),
                    "http://127.0.0.1:9999",
                )
                self.assertTrue(mock_get.call_args[0][0].startswith("http://127.0.0.1:9999/"))


if __name__ == "__main__":
    unittest.main()
