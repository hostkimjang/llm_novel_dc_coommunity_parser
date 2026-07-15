from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools.run_independent_plan import (
    CHILD_LIVENESS_ACTIVE,
    CHILD_LIVENESS_EXITED,
    CHILD_LIVENESS_UNKNOWN,
    _active_plan_lock,
    _active_runtime_path_locks,
    _attempt_claim_payload,
    _attempt_file_paths,
    _child_started_path,
    _child_started_receipt_payload,
    _dashboard_enabled_from_cli,
    _execution_claim_contract,
    _file_sha256 as _runner_file_sha256,
    _plan_claim_payload,
    _planned_runtime_path_entries,
    _preflight_run_artifacts,
    _process_creation_token,
    _recorded_child_liveness,
    _resolve_path as _runner_resolve_path,
    _run_artifact_paths,
    _run_execution_paths,
    audit_plan_execution_adoption_contract,
    run_plan,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_fixture(
    root: Path,
    *,
    post_id: str = "501",
    side_effect_code: str = "",
) -> tuple[dict, dict[str, Path]]:
    paths = {
        "output_json": root / "result.json",
        "checkpoint_jsonl": root / "result_checkpoint.jsonl",
        "manifest_json": root / "result_manifest.json",
    }
    code = (side_effect_code + ";" if side_effect_code else "") + (
        "import json,sys; from pathlib import Path; "
        "o,c,m,p=map(Path,sys.argv[1:5]); rid='runner-test-'+p.name; "
        "o.parent.mkdir(parents=True,exist_ok=True); "
        "o.write_text(json.dumps([{'post_id':p.name,'run_meta':{'run_id':rid}}]),encoding='utf-8'); "
        "c.write_text(json.dumps({'post_id':p.name,'status':'completed'})+'\\n',encoding='utf-8'); "
        "m.write_text(json.dumps({'run_id':rid,'output_file':str(o),'checkpoint_jsonl':str(c),"
        "'input_post_count':1,'completed_count':1,'flushed_count':1,'pending_count':0,'failed_count':0}),encoding='utf-8')"
    )
    run = {
        "post_id": post_id,
        "repeat_index": 1,
        **{field: str(path) for field, path in paths.items()},
        "command_argv": [
            sys.executable,
            "-c",
            code,
            str(paths["output_json"]),
            str(paths["checkpoint_jsonl"]),
            str(paths["manifest_json"]),
            post_id,
        ],
    }
    return run, paths


def _write_plan(path: Path, run: dict) -> None:
    path.write_text(json.dumps({"planned_runs": [run]}), encoding="utf-8")


def _materialize_global_claim(plan_path: Path) -> tuple[dict, list, dict, Path, dict]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    runs = plan["planned_runs"]
    contract = _execution_claim_contract(plan_path=plan_path, plan=plan, runs=runs)
    claim_path = _runner_resolve_path(contract["persistent_plan_claim_json"])
    claim = _plan_claim_payload(
        plan_path=plan_path,
        plan=plan,
        runs=runs,
        contract=contract,
    )
    claim_path.parent.mkdir(parents=True, exist_ok=True)
    claim_path.write_text(
        json.dumps(claim, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return plan, runs, contract, claim_path, claim


def _materialize_indeterminate_started_attempt(plan_path: Path, *, run_index: int = 1):
    plan, runs, contract, global_claim_path, global_claim = _materialize_global_claim(
        plan_path
    )
    run = runs[run_index - 1]
    artifact_paths = _run_artifact_paths(run, index=run_index)
    execution_paths = _run_execution_paths(
        contract=contract, run=run, index=run_index
    )
    claim_path, _terminal_path = _attempt_file_paths(
        execution_paths["attempt_dir"], 1
    )
    attempt_claim = _attempt_claim_payload(
        run=run,
        index=run_index,
        attempt_index=1,
        plan_sha256=global_claim["plan_sha256"],
        global_claim_sha256=_runner_file_sha256(global_claim_path),
        artifact_paths=artifact_paths,
    )
    claim_path.parent.mkdir(parents=True, exist_ok=True)
    claim_path.write_text(
        json.dumps(attempt_claim, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    child_path = _child_started_path(execution_paths["attempt_dir"], 1)
    child = _child_started_receipt_payload(
        claim_path=claim_path,
        claim=attempt_claim,
        child_pid=424242,
        process_creation_token="test-crashed-child-token",
    )
    child_path.write_text(
        json.dumps(child, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return run, artifact_paths, execution_paths


class RunIndependentPlanTest(unittest.TestCase):
    def test_script_path_invocation_imports_tools_package(self):
        repo_root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [sys.executable, str(repo_root / "tools" / "run_independent_plan.py"), "--help"],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--set-env", proc.stdout)

    def test_cli_no_dashboard_is_forced_on_without_breakglass_env(self):
        self.assertEqual(
            _dashboard_enabled_from_cli(True, env={}),
            (True, "forced_on_no_dashboard_forbidden"),
        )
        self.assertEqual(
            _dashboard_enabled_from_cli(
                True, env={"ALLOW_TEST_RUN_NO_DASHBOARD": "1"}
            ),
            (False, "breakglass_disabled"),
        )
        self.assertEqual(
            _dashboard_enabled_from_cli(False, env={}),
            (True, "default_on"),
        )

    def test_runner_disables_interactive_llm_watchdog_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_path = root / "env.txt"
            side_effect = (
                "import os,pathlib;"
                f"pathlib.Path({str(env_path)!r}).write_text("
                "os.environ.get('LLM_SUSPEND_ON_SERVER_ANOMALY','')+'|'+"
                "os.environ.get('LLM_SUSPEND_FAILURE_THRESHOLD','')+'|'+"
                "os.environ.get('LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS','')+'|'+"
                "os.environ.get('LLM_STREAM_IDLE_TIMEOUT_SECONDS',''),encoding='utf-8')"
            )
            run, _paths = _run_fixture(root, side_effect_code=side_effect)
            plan_path = root / "plan.json"
            _write_plan(plan_path, run)
            rc = run_plan(
                plan_path=plan_path,
                log_dir=root / "logs",
                env_updates={},
                skip_existing=False,
                limit=None,
                dashboard=False,
            )
            self.assertEqual(rc, 0)
            self.assertEqual(env_path.read_text(encoding="utf-8"), "0|0|45|45")

    def test_plan_and_run_env_overrides_are_forwarded_to_child_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_path = root / "env.txt"
            side_effect = (
                "import os,pathlib;"
                f"pathlib.Path({str(env_path)!r}).write_text("
                "os.environ.get('MCP_HEALTH_INCLUDE_SEARCH','')+'|'+"
                "os.environ.get('MCP_HEALTH_LIGHT_MODE','')+'|'+"
                "os.environ.get('MCP_HEALTH_REQUIRED_OK','')+'|'+"
                "os.environ.get('MCP_HEALTH_PROBE_BATCH_SIZE',''),encoding='utf-8')"
            )
            run, _paths = _run_fixture(root, side_effect_code=side_effect)
            run["env_overrides"] = {"MCP_HEALTH_PROBE_BATCH_SIZE": "16"}
            plan_path = root / "plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "required_env": {"MCP_HEALTH_INCLUDE_SEARCH": "1"},
                        "runtime_contract": {
                            "required_env": {
                                "MCP_HEALTH_LIGHT_MODE": "0",
                                "MCP_HEALTH_REQUIRED_OK": "16",
                            }
                        },
                        "planned_runs": [run],
                    }
                ),
                encoding="utf-8",
            )
            rc = run_plan(
                plan_path=plan_path,
                log_dir=root / "logs",
                env_updates={},
                skip_existing=False,
                limit=None,
                dashboard=False,
            )
            self.assertEqual(rc, 0)
            self.assertEqual(env_path.read_text(encoding="utf-8"), "1|0|16|16")

    def test_runner_defaults_to_dashboard_mode_sets_forwarding_env_and_strips_no_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_path = root / "env.txt"
            side_effect = (
                "import os,pathlib,sys;"
                f"pathlib.Path({str(env_path)!r}).write_text("
                "os.environ.get('DASHBOARD_URL','')+'|'+"
                "os.environ.get('DASHBOARD_PORT','')+'|'+"
                "os.environ.get('EXPERT_DASHBOARD_FORWARD','')+'|'+"
                "str('--no-dashboard' in sys.argv),encoding='utf-8')"
            )
            run, _paths = _run_fixture(root, side_effect_code=side_effect)
            run["command_argv"].append("--no-dashboard")
            plan_path = root / "plan.json"
            _write_plan(plan_path, run)
            with patch(
                "tools.run_independent_plan._ensure_dashboard",
                return_value={
                    "status": "already_running",
                    "ok": True,
                    "standalone": True,
                    "url": "http://127.0.0.1:18080",
                },
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    rc = run_plan(
                        plan_path=plan_path,
                        log_dir=root / "logs",
                        env_updates={},
                        skip_existing=False,
                        limit=None,
                        dashboard_url="http://127.0.0.1:18080",
                        dashboard_python=sys.executable,
                    )
            self.assertEqual(rc, 0)
            self.assertEqual(
                env_path.read_text(encoding="utf-8"),
                "http://127.0.0.1:18080|18080|1|False",
            )
            self.assertIn('"event": "dashboard_ready"', output.getvalue())
            self.assertIn('"dashboard_url": "http://127.0.0.1:18080"', output.getvalue())
            dashboard_markers = list(
                (root / "logs" / "attempts").glob("*/dashboard.marker.log")
            )
            self.assertEqual(len(dashboard_markers), 1)
            self.assertIn(
                "status=already_running",
                dashboard_markers[0].read_text(encoding="utf-8"),
            )

    def test_runner_starts_manifest_attach_for_dashboard_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, _paths = _run_fixture(root)
            plan_path = root / "plan.json"
            _write_plan(plan_path, run)
            with patch(
                "tools.run_independent_plan._ensure_dashboard",
                return_value={
                    "status": "already_running",
                    "ok": True,
                    "standalone": True,
                    "url": "http://127.0.0.1:18080",
                },
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    rc = run_plan(
                        plan_path=plan_path,
                        log_dir=root / "logs",
                        env_updates={},
                        skip_existing=False,
                        limit=None,
                        dashboard_url="http://127.0.0.1:18080",
                        dashboard_python=sys.executable,
                    )
            self.assertEqual(rc, 0)
            self.assertIn('"dashboard_attach_started_runs": 1', output.getvalue())
            marker = next(
                (root / "logs" / "attempts").glob("*/run_001_result.marker.log")
            )
            marker_text = marker.read_text(encoding="utf-8")
            self.assertIn("dashboard_attach_pid=", marker_text)
            self.assertIn(f"manifest={run['manifest_json']}", marker_text)
            attach_log = next(
                (root / "logs" / "attempts").glob(
                    "*/run_001_result.dashboard_attach.log"
                )
            )
            self.assertIn("START_ATTACH", attach_log.read_text(encoding="utf-8"))


class RunIndependentPlanExclusiveContractTest(unittest.TestCase):
    def test_first_execution_creates_receipt_once_and_refuses_any_existing_runtime_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, paths = _run_fixture(root)
            plan = root / "plan.json"
            log_dir = root / "logs"
            _write_plan(plan, run)

            rc = run_plan(
                plan_path=plan,
                log_dir=log_dir,
                env_updates={},
                skip_existing=False,
                limit=None,
                dashboard=False,
            )
            self.assertEqual(rc, 0)
            receipts = list(
                (log_dir / "attempts").glob("*/execution.receipt.json")
            )
            markers = list((log_dir / "attempts").glob("*/execution.marker.json"))
            self.assertEqual(len(receipts), 1)
            self.assertEqual(len(markers), 1)
            receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
            self.assertEqual(receipt["gate"], "GO")
            self.assertTrue(receipt["exclusive_create"])
            self.assertEqual(receipt["completed_runs"], 1)
            artifact_hashes = {field: _sha256(path) for field, path in paths.items()}
            receipt_hash = _sha256(receipts[0])
            marker_hash = _sha256(markers[0])

            with self.assertRaises(FileExistsError):
                run_plan(
                    plan_path=plan,
                    log_dir=log_dir,
                    env_updates={},
                    skip_existing=False,
                    limit=None,
                    dashboard=False,
                )
            self.assertEqual(
                {field: _sha256(path) for field, path in paths.items()}, artifact_hashes
            )
            self.assertEqual(_sha256(receipts[0]), receipt_hash)
            self.assertEqual(_sha256(markers[0]), marker_hash)

    def test_skip_existing_verifies_complete_artifacts_and_records_immutable_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, paths = _run_fixture(root)
            plan = root / "plan.json"
            first_logs = root / "first-logs"
            resume_logs = first_logs
            _write_plan(plan, run)
            self.assertEqual(
                run_plan(
                    plan_path=plan,
                    log_dir=first_logs,
                    env_updates={},
                    skip_existing=False,
                    limit=None,
                    dashboard=False,
                ),
                0,
            )
            artifact_hashes = {field: _sha256(path) for field, path in paths.items()}

            self.assertEqual(
                run_plan(
                    plan_path=plan,
                    log_dir=resume_logs,
                    env_updates={},
                    skip_existing=True,
                    limit=None,
                    dashboard=False,
                ),
                0,
            )
            receipts = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in (resume_logs / "attempts").glob("*/execution.receipt.json")
            ]
            receipt = next(item for item in receipts if item.get("skipped_adopted_before") == 1)
            self.assertEqual(receipt["completed_runs"], 0)
            self.assertEqual(receipt["adopted_total"], 1)
            self.assertEqual(
                {field: _sha256(path) for field, path in paths.items()}, artifact_hashes
            )

            different_log_dir = root / "different-resume-logs"
            self.assertEqual(
                run_plan(
                    plan_path=plan,
                    log_dir=different_log_dir,
                    env_updates={},
                    skip_existing=True,
                    limit=None,
                    dashboard=False,
                ),
                0,
            )
            different_receipt = json.loads(
                next(
                    (different_log_dir / "attempts").glob(
                        "*/execution.receipt.json"
                    )
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(different_receipt["gate"], "GO")
            self.assertEqual(different_receipt["selected_runs"], 0)

            mutated = json.loads(paths["output_json"].read_text(encoding="utf-8"))
            mutated[0]["tampered_after_receipt"] = True
            paths["output_json"].write_text(json.dumps(mutated), encoding="utf-8")
            mutated_hash = _sha256(paths["output_json"])
            with self.assertRaisesRegex(ValueError, "artifact hash mismatch"):
                run_plan(
                    plan_path=plan,
                    log_dir=resume_logs,
                    env_updates={},
                    skip_existing=True,
                    limit=None,
                    dashboard=False,
                )
            self.assertEqual(_sha256(paths["output_json"]), mutated_hash)

    def test_skip_existing_rejects_incomplete_or_mutated_artifacts_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, paths = _run_fixture(root)
            plan = root / "plan.json"
            _write_plan(plan, run)
            paths["output_json"].write_text("[]", encoding="utf-8")
            original_hash = _sha256(paths["output_json"])
            with self.assertRaisesRegex(ValueError, "incomplete existing artifacts"):
                _preflight_run_artifacts([run], skip_existing=True)
            self.assertEqual(_sha256(paths["output_json"]), original_hash)

            paths["checkpoint_jsonl"].write_text(
                json.dumps({"post_id": run["post_id"], "status": "completed"}) + "\n",
                encoding="utf-8",
            )
            paths["manifest_json"].write_text(
                json.dumps(
                    {
                        "run_id": "tampered",
                        "output_file": str(paths["output_json"]),
                        "checkpoint_jsonl": str(paths["checkpoint_jsonl"]),
                        "input_post_count": 1,
                        "completed_count": 0,
                        "flushed_count": 1,
                        "pending_count": 0,
                        "failed_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            hashes = {field: _sha256(path) for field, path in paths.items()}
            with self.assertRaisesRegex(ValueError, "completed_count mismatch"):
                _preflight_run_artifacts([run], skip_existing=True)
            self.assertEqual({field: _sha256(path) for field, path in paths.items()}, hashes)


class RunIndependentPlanGlobalClaimTest(unittest.TestCase):
    def test_preexisting_global_claim_mismatch_fails_before_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, paths = _run_fixture(root)
            plan_path = root / "plan.json"
            _write_plan(plan_path, run)
            _plan, _runs, _contract, claim_path, claim = _materialize_global_claim(
                plan_path
            )
            claim["plan_sha256"] = "0" * 64
            claim_path.write_text(json.dumps(claim), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "persistent plan claim mismatch"):
                run_plan(
                    plan_path=plan_path,
                    log_dir=root / "logs",
                    env_updates={},
                    skip_existing=True,
                    limit=None,
                    dashboard=False,
                )
            self.assertFalse(any(path.exists() for path in paths.values()))

    def test_active_lock_blocks_different_log_dir_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, paths = _run_fixture(root)
            plan_path = root / "plan.json"
            _write_plan(plan_path, run)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            contract = _execution_claim_contract(
                plan_path=plan_path, plan=plan, runs=plan["planned_runs"]
            )
            lock_path = _runner_resolve_path(contract["active_lock_file"])
            with _active_plan_lock(lock_path):
                with self.assertRaisesRegex(RuntimeError, "active plan lock already held"):
                    run_plan(
                        plan_path=plan_path,
                        log_dir=root / "different-log-dir",
                        env_updates={},
                        skip_existing=True,
                        limit=None,
                        dashboard=False,
                    )
            self.assertFalse(any(path.exists() for path in paths.values()))

    def test_duplicate_runtime_path_across_runs_and_fields_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run1, paths1 = _run_fixture(root / "run1", post_id="501")
            run2, paths2 = _run_fixture(root / "run2", post_id="502")
            run2["checkpoint_jsonl"] = run1["output_json"]
            plan_path = root / "plan.json"
            plan_path.write_text(
                json.dumps({"planned_runs": [run1, run2]}), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "duplicate runtime artifact paths"):
                run_plan(
                    plan_path=plan_path,
                    log_dir=root / "logs",
                    env_updates={},
                    skip_existing=False,
                    limit=None,
                    dashboard=False,
                )
            self.assertFalse(any(path.exists() for path in paths1.values()))
            self.assertFalse(any(path.exists() for path in paths2.values()))

    def test_different_plan_same_runtime_path_active_lock_is_global(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, paths = _run_fixture(root / "shared")
            plan_a = root / "plan-a.json"
            plan_b = root / "plan-b.json"
            _write_plan(plan_a, run)
            _write_plan(plan_b, run)
            plan_a_payload = json.loads(plan_a.read_text(encoding="utf-8"))
            entries = _planned_runtime_path_entries(plan_a_payload["planned_runs"])
            with _active_runtime_path_locks(entries):
                with self.assertRaisesRegex(
                    RuntimeError, "active runtime path lock already held"
                ):
                    run_plan(
                        plan_path=plan_b,
                        log_dir=root / "plan-b-logs",
                        env_updates={},
                        skip_existing=False,
                        limit=None,
                        dashboard=False,
                    )
            self.assertFalse(any(path.exists() for path in paths.values()))

    def test_different_plan_same_runtime_path_persistent_claim_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a, paths = _run_fixture(root / "shared")
            run_a["command_argv"] = [sys.executable, "-c", "raise SystemExit(7)"]
            plan_a = root / "plan-a.json"
            _write_plan(plan_a, run_a)
            self.assertEqual(
                run_plan(
                    plan_path=plan_a,
                    log_dir=root / "plan-a-logs",
                    env_updates={},
                    skip_existing=False,
                    limit=None,
                    dashboard=False,
                ),
                7,
            )
            marker = root / "plan-b-child-started.txt"
            run_b, _ = _run_fixture(
                root / "shared",
                side_effect_code=f"from pathlib import Path; Path({str(marker)!r}).write_text('started')",
            )
            plan_b = root / "plan-b.json"
            _write_plan(plan_b, run_b)
            with self.assertRaisesRegex(
                ValueError, "persistent runtime path claim mismatch"
            ):
                run_plan(
                    plan_path=plan_b,
                    log_dir=root / "plan-b-logs",
                    env_updates={},
                    skip_existing=False,
                    limit=None,
                    dashboard=False,
                )
            self.assertFalse(marker.exists())
            self.assertFalse(any(path.exists() for path in paths.values()))

    def test_child_liveness_tracks_sleeping_then_exited_process(self):
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        receipt = {
            "child_pid": proc.pid,
            "process_creation_token": _process_creation_token(proc),
        }
        try:
            self.assertEqual(
                _recorded_child_liveness(receipt), CHILD_LIVENESS_ACTIVE
            )
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        self.assertEqual(_recorded_child_liveness(receipt), CHILD_LIVENESS_EXITED)

    def test_fallback_token_and_windows_query_unknown_are_fail_closed(self):
        fallback = {
            "child_pid": 424242,
            "process_creation_token": "pid-observed:424242:1",
        }
        with patch("tools.run_independent_plan._query_windows_process") as query:
            with patch("tools.run_independent_plan.os.name", "nt"):
                self.assertEqual(
                    _recorded_child_liveness(fallback), CHILD_LIVENESS_UNKNOWN
                )
            query.assert_not_called()
        with patch(
            "tools.run_independent_plan._query_windows_process",
            return_value=(CHILD_LIVENESS_UNKNOWN, None),
        ):
            with patch("tools.run_independent_plan.os.name", "nt"):
                self.assertEqual(
                    _recorded_child_liveness(
                        {
                            "child_pid": 424242,
                            "process_creation_token": "windows-filetime:1",
                        }
                    ),
                    CHILD_LIVENESS_UNKNOWN,
                )

    def test_complete_artifacts_with_fallback_token_are_not_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, _paths = _run_fixture(root)
            plan_path = root / "plan.json"
            _write_plan(plan_path, run)
            run, _artifact_paths, execution_paths = (
                _materialize_indeterminate_started_attempt(plan_path)
            )
            completed = subprocess.run(run["command_argv"], check=False)
            self.assertEqual(completed.returncode, 0)
            with self.assertRaisesRegex(ValueError, "UNKNOWN; recovery forbidden"):
                run_plan(
                    plan_path=plan_path,
                    log_dir=root / "recovery-logs",
                    env_updates={},
                    skip_existing=True,
                    limit=None,
                    dashboard=False,
                )
            self.assertFalse(execution_paths["adoption_receipt"].exists())

    def test_observed_child_rc_failure_is_terminal_and_never_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, paths = _run_fixture(root)
            run["command_argv"] = [sys.executable, "-c", "raise SystemExit(7)"]
            plan_path = root / "plan.json"
            _write_plan(plan_path, run)
            self.assertEqual(
                run_plan(
                    plan_path=plan_path,
                    log_dir=root / "first-logs",
                    env_updates={},
                    skip_existing=False,
                    limit=None,
                    dashboard=False,
                ),
                7,
            )
            self.assertFalse(any(path.exists() for path in paths.values()))
            terminal_path = next(
                root.glob(
                    ".plan.independent_plan_execution/attempts/*/attempt_001.terminal.json"
                )
            )
            terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
            self.assertEqual(terminal["status"], "FAILED_CHILD_RC")
            with self.assertRaisesRegex(ValueError, "final and not retryable"):
                run_plan(
                    plan_path=plan_path,
                    log_dir=root / "different-logs",
                    env_updates={},
                    skip_existing=True,
                    limit=None,
                    dashboard=False,
                )
            claims = list(
                root.glob(
                    ".plan.independent_plan_execution/attempts/*/attempt_*.claim.json"
                )
            )
            self.assertEqual(len(claims), 1)

    def test_complete_artifacts_without_terminal_are_recovered_and_adopted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, _paths = _run_fixture(root)
            plan_path = root / "plan.json"
            _write_plan(plan_path, run)
            run, artifact_paths, execution_paths = _materialize_indeterminate_started_attempt(
                plan_path
            )
            completed = subprocess.run(run["command_argv"], check=False)
            self.assertEqual(completed.returncode, 0)
            self.assertFalse(execution_paths["adoption_receipt"].exists())
            with patch(
                "tools.run_independent_plan._recorded_child_liveness",
                return_value=CHILD_LIVENESS_EXITED,
            ):
                self.assertEqual(
                    run_plan(
                        plan_path=plan_path,
                        log_dir=root / "recovery-logs",
                        env_updates={},
                        skip_existing=True,
                        limit=None,
                        dashboard=False,
                    ),
                    0,
                )
            self.assertTrue(execution_paths["adoption_receipt"].is_file())
            terminal_path = _attempt_file_paths(execution_paths["attempt_dir"], 1)[1]
            terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
            self.assertEqual(terminal["status"], "RECOVERED_COMPLETE")
            self.assertTrue(all(path.is_file() for path in artifact_paths.values()))
            receipt = json.loads(
                next(
                    (root / "recovery-logs" / "attempts").glob(
                        "*/execution.receipt.json"
                    )
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["gate"], "GO")
            self.assertEqual(receipt["selected_runs"], 0)

    def test_indeterminate_partial_artifact_is_never_reexecuted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, _paths = _run_fixture(root)
            plan_path = root / "plan.json"
            _write_plan(plan_path, run)
            _run, artifact_paths, execution_paths = _materialize_indeterminate_started_attempt(
                plan_path
            )
            artifact_paths["output_json"].write_text("[]", encoding="utf-8")
            output_hash = _sha256(artifact_paths["output_json"])
            with self.assertRaisesRegex(ValueError, "INDETERMINATE"):
                run_plan(
                    plan_path=plan_path,
                    log_dir=root / "resume-logs",
                    env_updates={},
                    skip_existing=True,
                    limit=None,
                    dashboard=False,
                )
            self.assertEqual(_sha256(artifact_paths["output_json"]), output_hash)
            self.assertFalse(execution_paths["adoption_receipt"].exists())

    def test_limit_receipt_is_partial_and_next_resume_advances_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run1, paths1 = _run_fixture(root / "run1", post_id="501")
            run2, paths2 = _run_fixture(root / "run2", post_id="502")
            plan_path = root / "plan.json"
            plan_path.write_text(
                json.dumps({"planned_runs": [run1, run2]}), encoding="utf-8"
            )
            self.assertEqual(
                run_plan(
                    plan_path=plan_path,
                    log_dir=root / "limit-logs-1",
                    env_updates={},
                    skip_existing=False,
                    limit=1,
                    dashboard=False,
                ),
                0,
            )
            first_receipt = json.loads(
                next(
                    (root / "limit-logs-1" / "attempts").glob(
                        "*/execution.receipt.json"
                    )
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(first_receipt["gate"], "PARTIAL_NOT_COMPLETE")
            self.assertEqual(first_receipt["selected_plan_indices"], [1])
            self.assertTrue(all(path.is_file() for path in paths1.values()))
            self.assertFalse(any(path.exists() for path in paths2.values()))

            self.assertEqual(
                run_plan(
                    plan_path=plan_path,
                    log_dir=root / "limit-logs-2",
                    env_updates={},
                    skip_existing=True,
                    limit=1,
                    dashboard=False,
                ),
                0,
            )
            second_receipt = json.loads(
                next(
                    (root / "limit-logs-2" / "attempts").glob(
                        "*/execution.receipt.json"
                    )
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(second_receipt["gate"], "GO")
            self.assertEqual(second_receipt["selected_plan_indices"], [2])
            self.assertEqual(second_receipt["adopted_total"], 2)

    def test_analyzer_rejects_duplicate_or_unrecorded_attempt_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for mutation in ("duplicate_claim", "terminal_without_claim"):
                with self.subTest(mutation=mutation):
                    folder = root / mutation
                    folder.mkdir(parents=True, exist_ok=True)
                    run, _paths = _run_fixture(folder)
                    plan_path = folder / "plan.json"
                    _write_plan(plan_path, run)
                    self.assertEqual(
                        run_plan(
                            plan_path=plan_path,
                            log_dir=folder / "logs",
                            env_updates={},
                            skip_existing=False,
                            limit=None,
                            dashboard=False,
                        ),
                        0,
                    )
                    plan = json.loads(plan_path.read_text(encoding="utf-8"))
                    contract = _execution_claim_contract(
                        plan_path=plan_path,
                        plan=plan,
                        runs=plan["planned_runs"],
                    )
                    execution_paths = _run_execution_paths(
                        contract=contract, run=run, index=1
                    )
                    claim1, terminal1 = _attempt_file_paths(
                        execution_paths["attempt_dir"], 1
                    )
                    claim2, terminal2 = _attempt_file_paths(
                        execution_paths["attempt_dir"], 2
                    )
                    if mutation == "duplicate_claim":
                        claim2.write_bytes(claim1.read_bytes())
                    else:
                        terminal2.write_bytes(terminal1.read_bytes())
                    audit = audit_plan_execution_adoption_contract(
                        plan_path=plan_path, plan=plan
                    )
                    self.assertEqual(audit["gate"], "NO-GO")
                    if mutation == "terminal_without_claim":
                        self.assertGreater(
                            audit["summary"]["unrecorded_attempt_count"], 0
                        )


if __name__ == "__main__":
    unittest.main()
