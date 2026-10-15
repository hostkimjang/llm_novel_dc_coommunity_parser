"""중첩 이력·실행 결속·관측 상태의 API 회귀 계약. 원격 호출은 없다."""
from __future__ import annotations

from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from llm_batch.monitor import server
from llm_batch.monitor.run_index import RunIndex, bound_manifest, row_meta, summary


RID = "20261007_204136_138377"
OLD_RID = "20260922_234704_270181"


def row(title="현재", *, run_id=RID, scope="scope-a"):
    return {
        "post_id": 7, "title": title,
        "analysis_result": {"identity": {"reason": "판정", "is_relevant": True},
                            "analysis": {"notes": "독립 메모", "is_nsfw": False}},
        "run_meta": {
            "run_id": run_id,
            "decision_call_ledger": {"publication_scope_id": scope},
            "decision_call_attempt_receipt": {"publication_link_status": "PENDING_EXTERNAL_LEDGER_LINK"},
            "decision_call_ledger_summary": {"actual_kpi_status": "PENDING_INDEPENDENT_READBACK", "actual_metrics": {"total_tokens": None}},
            "execution_config": {"schema_version": "expert_execution_config_v1"},
            "source_context_diagnostics": {"schema_version": "source_context_diagnostics_v1", "status": "OFF", "publication_authority": False},
            "llm_endpoint": "http://private/?token=DO_NOT_FORWARD",
        },
    }


class State:
    def __init__(self, output):
        self.output = output

    def get_status(self):
        return {"output_file": str(self.output)}

    def get_result_summary(self, post_id):
        return {"post_id": post_id, "title": "실행 중 요약"}


class RunIndexContract(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.out = self.root / "out"
        self.logs = self.root / "logs"
        self.out.mkdir()
        self.logs.mkdir()
        self.index = RunIndex()
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(server, "_OUT_DIR", self.out))
        self.stack.enter_context(patch.object(server, "_LOG_DIR", self.logs))
        self.stack.enter_context(patch.object(server, "_run_index", self.index))
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.stack.close()
        self.tmp.cleanup()

    def result(self, relative="axis/run/result.json", *, run_id=RID, scope="scope-a", rows=None, **fields):
        path = self.out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows if rows is not None else [row(run_id=run_id, scope=scope)], ensure_ascii=False), encoding="utf-8")
        manifest = path.with_name(f"{path.stem}_manifest.json")
        payload = {
            "output_file": str(path), "run_id": run_id, "publication_scope_id": scope,
            "terminal_artifacts_finalized": True, "completed_count": 1,
            "publication_execution_mode": "NORMAL_PUBLICATION_OWNER",
            "decision_call_ledger_summary": {"actual_kpi_status": "NOT_ESTIMABLE", "linked_row_attempt_count": 1, "actual_metrics": {"total_tokens": None}},
            "execution_config": {"schema_version": "expert_execution_config_v1"},
            **fields,
        }
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        return path, manifest, payload

    async def runs(self):
        response = await self.client.get("/api/runs")
        self.assertEqual(response.status_code, 200)
        return response.json()

    async def test_nested_and_legacy_history_keep_separate_keys_and_backward_routes(self):
        self.result("one/result.json")
        self.result("two/result.json", run_id=OLD_RID, rows=[row("이전", run_id=OLD_RID)])
        legacy = self.out / f"expert_result_{RID}.json"
        legacy.write_text(json.dumps([row("기존 형식")]), encoding="utf-8")
        runs = await self.runs()
        self.assertEqual(len(runs), 3)
        self.assertEqual(len({x["run_key"] for x in runs}), 3)
        for item in runs:
            page = await self.client.get(f"/api/runs/{item['run_key']}?summary=1")
            self.assertEqual(page.json()["total"], 1)
            detail = await self.client.get(f"/api/runs/{item['run_key']}/posts/7")
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["title"], "이전" if item["relative_path"] == "two/result.json" else "기존 형식" if item["filename"] == legacy.name else "현재")
        raw = await self.client.get(f"/api/runs/{legacy.name}")
        self.assertIsInstance(raw.json(), list)
        self.assertEqual((await self.client.get("/api/runs/result.json")).status_code, 404)

    async def test_live_and_history_expose_whitelist_without_rewriting_row_or_kpi(self):
        path, manifest, payload = self.result()
        before = (path.read_bytes(), manifest.read_bytes())
        self.stack.enter_context(patch.object(server, "monitor", State(path)))
        live = (await self.client.get("/api/results/7")).json()
        key = (await self.runs())[0]["run_key"]
        history = (await self.client.get(f"/api/runs/{key}/posts/7")).json()
        for detail in (live, history):
            self.assertNotIn("llm_endpoint", detail["run_meta"])
            self.assertEqual(detail["run_meta"]["decision_call_attempt_receipt"]["publication_link_status"], "PENDING_EXTERNAL_LEDGER_LINK")
            self.assertEqual(detail["run_meta"]["source_context_diagnostics"]["status"], "OFF")
            self.assertEqual(detail["run_manifest"]["binding_status"], "BOUND")
            self.assertEqual(detail["run_manifest"]["summary"]["decision_call_ledger_summary"]["actual_kpi_status"], "NOT_ESTIMABLE")
            self.assertIsNone(detail["run_manifest"]["summary"]["decision_call_ledger_summary"]["actual_metrics"]["total_tokens"])
        self.assertEqual(live["analysis_notes"], "독립 메모")
        self.assertFalse(live["analysis"]["is_nsfw"])
        self.assertEqual(before, (path.read_bytes(), manifest.read_bytes()))

    async def test_completion_counters_preserve_types_in_live_history_and_index(self):
        cases = {
            "complete": {"input_post_count": 1, "completed_count": 1, "flushed_count": 1,
                         "pending_count": 0, "failed_count": 0, "terminal_artifacts_finalized": True},
            "progress": {"input_post_count": 3, "completed_count": 2, "flushed_count": 1,
                         "pending_count": 1, "failed_count": 0, "terminal_artifacts_finalized": False},
            "failed": {"input_post_count": 2, "completed_count": 2, "flushed_count": 2,
                       "pending_count": 0, "failed_count": 1, "terminal_artifacts_finalized": True},
            "pending": {"input_post_count": 2, "completed_count": 2, "flushed_count": 1,
                        "pending_count": 1, "failed_count": 0, "terminal_artifacts_finalized": True},
            "invalid": {"input_post_count": True, "completed_count": "1", "flushed_count": -1,
                        "pending_count": False, "failed_count": {}, "terminal_artifacts_finalized": "true"},
            "missing": {},
            "null": {"input_post_count": None, "completed_count": None, "flushed_count": None,
                     "pending_count": None, "failed_count": None, "terminal_artifacts_finalized": None},
        }
        fields = ("input_post_count", "completed_count", "flushed_count", "pending_count",
                  "failed_count", "terminal_artifacts_finalized")
        files = {}
        for name, values in cases.items():
            path, manifest, payload = self.result(f"completion/{name}/result.json")
            for field in fields:
                payload.pop(field, None)
            payload.update(values)
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            files[name] = (path, manifest)
        records = {record["relative_path"]: record for record in await self.runs()}
        for name, expected in cases.items():
            with self.subTest(name=name):
                path, manifest = files[name]
                before = (path.read_bytes(), manifest.read_bytes())
                record = records[f"completion/{name}/result.json"]
                with patch.object(server, "monitor", State(path)):
                    live = (await self.client.get("/api/results/7")).json()
                history = (await self.client.get(f"/api/runs/{record['run_key']}/posts/7")).json()
                page = (await self.client.get(f"/api/runs/{record['run_key']}?summary=1")).json()
                for detail in (live, history, page):
                    self.assertEqual(detail["run_manifest"]["binding_status"], "BOUND")
                    self.assertEqual(detail["run_manifest"]["artifact_kind"], "RESULT")
                for view in (live["run_manifest"]["summary"], history["run_manifest"]["summary"],
                             page["run_manifest"]["summary"], record["manifest_summary"]):
                    projected = {field: view[field] for field in fields if field in view}
                    # JSON 타입까지 대조한다. True == 1 같은 Python 동등 비교를 쓰지 않는다.
                    self.assertEqual(json.dumps(projected, sort_keys=True), json.dumps(expected, sort_keys=True))
                    self.assertNotIn("completion_status", view)
                self.assertEqual(before, (path.read_bytes(), manifest.read_bytes()))

    async def test_manifest_binding_mismatch_does_not_attach_foreign_summary(self):
        path, _, _ = self.result(rows=[row(run_id=OLD_RID, scope="different")])
        self.stack.enter_context(patch.object(server, "monitor", State(path)))
        detail = (await self.client.get("/api/results/7")).json()
        self.assertEqual(detail["run_manifest"]["binding_status"], "MISMATCH")
        self.assertEqual(detail["run_manifest"]["summary"], {})
        self.assertIn("RUN_ID_MISMATCH", detail["run_manifest"]["reason_codes"])
        self.assertIn("PUBLICATION_SCOPE_MISMATCH", detail["run_manifest"]["reason_codes"])

    async def test_semantic_receipts_and_activation_keep_live_history_provenance(self):
        saved = row()
        binding = {"publication_scope_id": "scope-a", "input_index": 1, "post_id": 7,
                   "attempt_run_id": RID, "public_apply": False, "publication_decision_id": "decision-a"}
        review = {**binding, "schema_version": "semantic_review_router_receipt_v1", "mode": "REVIEW_ONLY",
                  "state": "REVIEW_REQUIRED", "trigger_codes": ["OCR_TITLE_UNRESOLVED"], "unknown_reason_codes": []}
        plan = {**binding, "schema_version": "semantic_recovery_plan_receipt_v1", "mode": "PLAN_ONLY",
                "plan": {"state": "HOLD", "query_plan": {"query_execution_allowed": False, "max_queries": 0},
                         "search_calls_executed": 0, "network_calls_executed": 0}}
        saved["run_meta"].update(semantic_review_router_receipt=review, semantic_recovery_plan_receipt=plan)
        activation = {"recovery_activation_schema": "review_recovery_activation_ledger_v1",
                      "recovery_activation_requested_mode": "AUDIT_ONLY", "recovery_activation_mode": "AUDIT_ONLY",
                      "recovery_activation_public_apply": False, "recovery_activation_status": "READY",
                      "recovery_activation_journal": "saved-sidecar.jsonl", "recovery_activation_event_count": 0,
                      "recovery_activation_proposals_observed": 0, "recovery_activation_events_created": 0,
                      "recovery_activation_events_replayed": 0, "recovery_activation_append_errors": 0,
                      "recovery_activation_tail_repair_count": 0, "recovery_activation_error_samples": []}
        path, manifest, _ = self.result(rows=[saved], **activation, recovery_activation_hmac_key="DO_NOT_FORWARD")
        before = (path.read_bytes(), manifest.read_bytes())
        self.stack.enter_context(patch.object(server, "monitor", State(path)))
        live = (await self.client.get("/api/results/7")).json()
        runs = await self.runs()
        key = runs[0]["run_key"]
        history = (await self.client.get(f"/api/runs/{key}/posts/7")).json()
        page = (await self.client.get(f"/api/runs/{key}?summary=1")).json()
        for detail in (live, history):
            self.assertEqual(detail["run_meta"]["semantic_review_router_receipt"], review)
            self.assertEqual(detail["run_meta"]["semantic_recovery_plan_receipt"], plan)
            self.assertNotIn("recovery_activation_status", detail["run_meta"])
            self.assertEqual(detail["run_manifest"]["binding_status"], "BOUND")
        for projected in (live["run_manifest"]["summary"], history["run_manifest"]["summary"],
                          page["run_manifest"]["summary"], runs[0]["manifest_summary"]):
            self.assertEqual({key: projected[key] for key in activation}, activation)
            self.assertNotIn("recovery_activation_hmac_key", projected)
        self.assertEqual(before, (path.read_bytes(), manifest.read_bytes()))

    async def test_calibration_capture_live_history_preserve_saved_payload_and_policy(self):
        saved = row()
        binding = {"run_id": RID, "publication_scope_id": "scope-a", "input_index": 1,
                   "post_id": 7, "attempt_id": "attempt-a"}
        calibration = {"schema_version": "candidate_calibration_shadow_v1", "mode": "SHADOW",
                       "status": "CALIBRATED_SHADOW_BOUND", "binding": binding, "post_id": 7,
                       "dataset_post_id": "dataset-seven", "dataset_example_id": "frozen-seven",
                       "publication_authority": False, "public_apply": False,
                       "calibration_shadow": {"probability_status": "CALIBRATED_SHADOW_BOUND",
                                              "action_applied": False, "event_probabilities": [
                                                  {"label": "__NIL__", "probability_mass": 0,
                                                   "probability_scale": 1000000}]}}
        # 존재하지 않는 참조도 metadata로 보존하며 API는 path를 따라 읽지 않는다.
        capture = {"schema_version": "candidate_reranker_capture_ref_v1", "mode": "SHADOW",
                   "status": "SAVED", "post_id": 7, "binding": binding, "publication_authority": False,
                   "fragment_count": 0, "candidate_count": 0,
                   "artifact": {"path": "../../not-read-capture.json", "sha256": "f" * 64, "bytes": 0}}
        policy = {"mode": "SHADOW", "status": "AVAILABLE", "scope": "FROZEN_REOBSERVATION_ONLY",
                  "data_kind": "SYNTHETIC_FIXTURE", "actual_quality_evaluated": False,
                  "publication_authority": False, "bundle_sha256": "b" * 64}
        saved["run_meta"].update(candidate_calibration_shadow=calibration, candidate_reranker_capture=capture)
        path, manifest, _ = self.result(rows=[saved], candidate_calibration_policy=policy)
        before = (path.read_bytes(), manifest.read_bytes())
        self.stack.enter_context(patch.object(server, "monitor", State(path)))
        live = (await self.client.get("/api/results/7")).json()
        runs = await self.runs()
        key = runs[0]["run_key"]
        history = (await self.client.get(f"/api/runs/{key}/posts/7")).json()
        page = (await self.client.get(f"/api/runs/{key}?summary=1")).json()
        for detail in (live, history):
            self.assertEqual(detail["run_meta"]["candidate_calibration_shadow"], calibration)
            self.assertEqual(detail["run_meta"]["candidate_reranker_capture"], capture)
            self.assertEqual(detail["run_manifest"]["binding_status"], "BOUND")
            self.assertEqual(detail["run_manifest"]["summary"]["candidate_calibration_policy"], policy)
        self.assertEqual(page["run_manifest"]["summary"]["candidate_calibration_policy"], policy)
        self.assertEqual(runs[0]["manifest_summary"]["candidate_calibration_policy"], policy)
        self.assertEqual(before, (path.read_bytes(), manifest.read_bytes()))

    def test_calibration_capture_binding_conflicts_reject_manifest_summary(self):
        path, _, _ = self.result()
        for field in ("candidate_calibration_shadow", "candidate_reranker_capture"):
            for key, foreign, reason in (("run_id", OLD_RID, "RUN_ID_ROW_CONFLICT"),
                                         ("publication_scope_id", "foreign-scope", "PUBLICATION_SCOPE_ROW_CONFLICT")):
                for location in ("binding", "top_level"):
                    with self.subTest(field=field, key=key, location=location):
                        saved = row()
                        observed = {"binding": {"run_id": RID, "publication_scope_id": "scope-a"}}
                        if location == "binding":
                            observed["binding"][key] = foreign
                        else:
                            observed[key] = foreign
                        saved["run_meta"][field] = observed
                        result = bound_manifest(path, self.out, item=saved)
                        self.assertEqual(result["binding_status"], "MISMATCH")
                        self.assertIn(reason, result["reason_codes"])
                        self.assertEqual(result["summary"], {})
        # 새 관측끼리 일치해도 선택 manifest와 다르면 거절한다.
        saved = {"run_meta": {"candidate_reranker_capture": {
            "binding": {"run_id": OLD_RID, "publication_scope_id": "foreign-scope"}}}}
        result = bound_manifest(path, self.out, item=saved)
        self.assertIn("RUN_ID_MISMATCH", result["reason_codes"])
        self.assertIn("PUBLICATION_SCOPE_MISMATCH", result["reason_codes"])

    def test_calibration_capture_projection_preserves_missing_null_and_not_executed(self):
        self.assertEqual(row_meta({}), {})
        for status in ("NOT_AVAILABLE", "NOT_EXECUTED", "UNAVAILABLE", "OFF", None):
            with self.subTest(status=status):
                meta = {"candidate_calibration_shadow": {"status": status, "calibration_shadow": None,
                                                         "action_applied": False},
                        "candidate_reranker_capture": {"status": status, "artifact": None},
                        "llm_endpoint": "DO_NOT_FORWARD"}
                self.assertEqual(row_meta({"run_meta": meta}), {k: v for k, v in meta.items() if k != "llm_endpoint"})
        self.assertEqual(summary({"candidate_calibration_policy": None}), {"candidate_calibration_policy": None})

    def test_recovery_projection_preserves_missing_false_zero_and_fresh_skip(self):
        self.assertEqual(row_meta({}), {})
        self.assertEqual(summary({}), {})
        for status, mode in (("DISABLED", "OFF"), ("SKIPPED_FRESH_MEASUREMENT", "AUDIT_ONLY"),
                             ("NO_GO", "INVALID"), (None, None)):
            fields = {"recovery_activation_status": status, "recovery_activation_mode": mode,
                      "recovery_activation_public_apply": False, "recovery_activation_event_count": 0}
            self.assertEqual(summary(fields), fields)

    def test_missing_or_internally_conflicting_row_bindings_are_explicit(self):
        path, _, _ = self.result()
        legacy = {"post_id": 7}
        self.assertEqual(bound_manifest(path, self.out, item=legacy)["binding_status"], "PARTIAL")
        conflicting = row()
        conflicting["run_meta"]["publication_scope_id"] = "other"
        result = bound_manifest(path, self.out, item=conflicting)
        self.assertEqual(result["binding_status"], "MISMATCH")
        self.assertIn("PUBLICATION_SCOPE_ROW_CONFLICT", result["reason_codes"])

    async def test_modes_final_partial_and_legacy_unknown_are_not_inferred_from_folder(self):
        self.result("actual/final/result.json")
        self.result("replay/partial/result.json", terminal_artifacts_finalized=False, publication_execution_mode="SAVED_CONTEXT_REPLAY")
        path, manifest, payload = self.result("actual/unknown/result.json")
        payload.pop("terminal_artifacts_finalized")
        payload.pop("publication_execution_mode")
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        records = {x["relative_path"]: x for x in await self.runs()}
        self.assertEqual(records["actual/final/result.json"]["completion_status"], "FINAL")
        self.assertEqual(records["replay/partial/result.json"]["completion_status"], "PARTIAL")
        self.assertEqual(records["replay/partial/result.json"]["execution_mode"], "SAVED_CONTEXT_REPLAY")
        self.assertEqual(records["actual/unknown/result.json"]["completion_status"], "UNKNOWN")
        self.assertEqual(records["actual/unknown/result.json"]["execution_mode"], "UNKNOWN")

    async def test_real_completed_subset_sidecar_is_distinguished_from_main_result(self):
        path, _, _ = self.result(terminal_artifacts_finalized=False)
        subset = path.with_name("result_completed_subset.json")
        subset.write_text(json.dumps([row("복구 부분집합")]), encoding="utf-8")
        subset.with_name("result_completed_subset_manifest.json").write_text(json.dumps({
            "output_file": str(path), "completed_subset_json": str(subset), "completed_subset_count": 1,
            "run_id": RID, "publication_scope_id": "scope-a", "reason": "ORDERED_FLUSH_GAP",
        }), encoding="utf-8")
        records = await self.runs()
        self.assertEqual(len(records), 2)
        record = next(x for x in records if x["artifact_kind"] == "COMPLETED_SUBSET")
        self.assertEqual(record["completion_status"], "PARTIAL")
        self.assertEqual(record["post_count"], 1)
        detail = (await self.client.get(f"/api/runs/{record['run_key']}/posts/7")).json()
        self.assertEqual(detail["run_manifest"]["binding_status"], "BOUND")
        self.assertEqual(detail["title"], "복구 부분집합")
        self.assertEqual(detail["run_manifest"]["artifact_kind"], "COMPLETED_SUBSET")

    async def test_repo_relative_output_requires_exact_sidecar_and_preserves_bytes(self):
        path, manifest, payload = self.result("actual50/run/result.json")
        payload["output_file"] = "out/actual50/run/result.json"
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        before = manifest.read_bytes()
        record = self.index._current_record(path, self.out)
        self.assertIsNotNone(record)
        records = await self.runs()
        self.assertEqual([r["relative_path"] for r in records], ["actual50/run/result.json"])
        detail = (await self.client.get(f"/api/runs/{records[0]['run_key']}/posts/7")).json()
        self.assertEqual(detail["run_manifest"]["binding_status"], "BOUND")
        self.assertEqual(detail["run_manifest"]["artifact_kind"], "RESULT")
        duplicate = self.out / "other_manifest.json"
        duplicate.write_bytes(before)
        self.assertEqual(bound_manifest(path, self.out, manifest_path=duplicate)["binding_status"], "MISMATCH")
        self.assertEqual(manifest.read_bytes(), before)

    async def test_repo_relative_output_rejects_ambiguity_and_parent_traversal(self):
        path, manifest, payload = self.result("actual/run/result.json")
        payload["output_file"] = "out/actual/run/result.json"
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        ambiguous = self.out / payload["output_file"]
        ambiguous.parent.mkdir(parents=True)
        ambiguous.write_text("[]", encoding="utf-8")
        self.assertIsNone(self.index._current_record(path, self.out))
        ambiguous.unlink()
        payload["output_file"] = "out/actual/../actual/run/result.json"
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        self.assertIsNone(self.index._current_record(path, self.out))

    async def test_repo_relative_output_rejects_symlink_escape(self):
        outside = self.root / "outside"
        outside.mkdir()
        target = outside / "result.json"
        target.write_text("[]", encoding="utf-8")
        link = self.out / "escape"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("OS does not permit symlink creation")
        manifest = self.out / "result_manifest.json"
        payload = {"output_file": "out/escape/result.json"}
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(bound_manifest(target, self.out, manifest_path=manifest)["binding_status"], "MISMATCH")

    async def test_untrusted_manifests_pending_snapshots_and_arbitrary_json_are_excluded(self):
        path, _, payload = self.result()
        (self.out / "duplicate_manifest.json").write_text(json.dumps(payload), encoding="utf-8")
        (self.out / "broken_manifest.json").write_text("{", encoding="utf-8")
        outside = self.root / "outside.json"
        outside.write_text("[]", encoding="utf-8")
        (self.out / "outside_manifest.json").write_text(json.dumps({"output_file": str(outside)}), encoding="utf-8")
        pending = path.with_name("result_pending_snapshot.json")
        pending.write_text("[]", encoding="utf-8")
        pending.with_name("result_pending_snapshot_manifest.json").write_text(json.dumps({"output_file": str(pending)}), encoding="utf-8")
        (self.out / "arbitrary.json").write_text("[]", encoding="utf-8")
        self.assertEqual(len(await self.runs()), 1)
        for key in ("run_" + "f" * 32, "outside.json", "..%5Coutside.json"):
            self.assertIn((await self.client.get(f"/api/runs/{key}")).status_code, (400, 404))

    async def test_symlink_target_outside_root_cannot_be_read_as_legacy_result(self):
        target = self.root / "outside.json"
        target.write_text(json.dumps([row()]), encoding="utf-8")
        link = self.out / f"expert_result_{RID}.json"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("OS does not permit symlink creation")
        self.assertEqual(await self.runs(), [])
        self.assertEqual((await self.client.get(f"/api/runs/{link.name}")).status_code, 404)

    async def test_selected_run_logs_and_reused_output_paths_do_not_cross_run(self):
        path, manifest, payload = self.result()
        for rid, text in ((RID, "CURRENT"), (OLD_RID, "OLD")):
            (self.logs / f"expert_run_{rid}.log").write_text(text, encoding="utf-8")
        key = (await self.runs())[0]["run_key"]
        log = (await self.client.get(f"/api/runs/{key}/log")).json()
        self.assertEqual(log["lines"], ["CURRENT"])
        payload["run_id"] = OLD_RID
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual((await self.client.get(f"/api/runs/{key}/posts/7")).status_code, 404)
        self.assertEqual((await self.client.get(f"/api/runs/{key}/log")).status_code, 404)

    async def test_stale_manifest_cannot_select_another_runs_log(self):
        self.result(rows=[row(run_id=OLD_RID)])
        (self.logs / f"expert_run_{RID}.log").write_text("WRONG RUN", encoding="utf-8")
        key = (await self.runs())[0]["run_key"]
        self.assertEqual((await self.client.get(f"/api/runs/{key}/log")).status_code, 404)

    async def test_cached_discovery_does_not_parse_large_nested_results_on_refresh(self):
        self.result()
        with patch.object(self.index, "_paths", wraps=self.index._paths) as paths, patch.object(self.index, "load_result", wraps=self.index.load_result) as loads:
            await self.runs()
            await self.runs()
        self.assertEqual(paths.call_count, 1)
        self.assertEqual(loads.call_count, 0)
        self.index._expires = 0
        self.result("new/result.json", run_id=OLD_RID)
        self.assertEqual(len(await self.runs()), 2)

    async def test_scan_limits_are_reported_without_recursive_unbounded_walk(self):
        self.result()
        self.index.max_entries = 0
        response = await self.client.get("/api/runs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-run-index-truncated"], "true")

    async def test_deep_ledger_does_not_starve_shallow_run_manifests(self):
        self.result("a_run/result.json")
        frames = self.out / "z_ledger" / "frames"
        frames.mkdir(parents=True)
        for index in range(60):
            (frames / f"{index}.json").write_text("{}", encoding="utf-8")
        self.index.max_entries = 20
        response = await self.client.get("/api/runs")
        self.assertEqual(response.headers["x-run-index-truncated"], "true")
        self.assertEqual([item["relative_path"] for item in response.json()], ["a_run/result.json"])

    async def test_history_aggregate_checks_all_rows_not_only_first(self):
        self.result(rows=[row(), {**row(scope="other-scope"), "post_id": 8}], completed_count=2)
        key = (await self.runs())[0]["run_key"]
        page = (await self.client.get(f"/api/runs/{key}?summary=1")).json()
        self.assertEqual(page["run_manifest"]["binding_status"], "MISMATCH")
        self.assertEqual(page["run_manifest"]["summary"], {})

    async def test_current_nested_run_survives_scan_limit_and_history_selection(self):
        path, _, _ = self.result()
        self.index.max_entries = 0
        with patch.object(server, "monitor", State(path)):
            response = await self.client.get("/api/runs")
            self.assertEqual(response.headers["x-run-index-truncated"], "true")
            self.assertEqual([r["relative_path"] for r in response.json()], ["axis/run/result.json"])
            key = response.json()[0]["run_key"]
            self.index._expires = 0
            page = (await self.client.get(f"/api/runs/{key}?summary=1")).json()
            self.assertEqual(page["run_manifest"]["binding_status"], "BOUND")
            self.assertEqual(page["items"][0]["post_id"], 7)

    async def test_current_run_changes_without_waiting_for_discovery_cache(self):
        path, _, _ = self.result("first/result.json")
        self.index.max_entries = 0
        state = State(path)
        with patch.object(server, "monitor", state):
            old_key = (await self.runs())[0]["run_key"]
            new_path, _, _ = self.result("second/result.json", run_id=OLD_RID)
            state.output = new_path
            runs = await self.runs()
            self.assertEqual({r["relative_path"] for r in runs}, {"first/result.json", "second/result.json"})
            new_key = next(r["run_key"] for r in runs if r["relative_path"] == "second/result.json")
            self.assertNotEqual(new_key, old_key)
            previous = await self.client.get(f"/api/runs/{old_key}?summary=1")
            self.assertEqual(previous.status_code, 200)
            self.assertEqual(previous.json()["run_manifest"]["binding_status"], "BOUND")
            self.assertEqual(previous.json()["items"][0]["post_id"], 7)

    async def test_current_run_requires_safe_output_and_matching_manifest(self):
        path, manifest, payload = self.result()
        other, _, _ = self.result("other/result.json")
        self.index.max_entries = 0
        state = State(path)
        with patch.object(server, "monitor", state):
            payload["output_file"] = str(other)
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(await self.runs(), [])
            manifest.unlink()
            self.assertEqual(await self.runs(), [])
            state.output = self.root / "outside.json"
            self.assertEqual(await self.runs(), [])

    async def test_current_run_refreshes_manifest_without_repeating_full_scan(self):
        path, manifest, payload = self.result(terminal_artifacts_finalized=False)
        self.index.max_entries = 0
        with patch.object(server, "monitor", State(path)), patch.object(self.index, "_paths", wraps=self.index._paths) as paths:
            self.assertEqual((await self.runs())[0]["completion_status"], "PARTIAL")
            payload["terminal_artifacts_finalized"] = True
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual((await self.runs())[0]["completion_status"], "FINAL")
            self.assertEqual(paths.call_count, 1)

    async def test_malformed_selected_result_is_reported_without_server_trace(self):
        path, _, _ = self.result()
        key = (await self.runs())[0]["run_key"]
        path.write_text("[ broken", encoding="utf-8")
        response = await self.client.get(f"/api/runs/{key}?summary=1")
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(str(self.root), response.text)


if __name__ == "__main__":
    unittest.main()
