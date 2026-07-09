import json
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools.run_independent_plan import _dashboard_enabled_from_cli, run_plan


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
            _dashboard_enabled_from_cli(True, env={"ALLOW_TEST_RUN_NO_DASHBOARD": "1"}),
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
            plan_path = root / "plan.json"
            code = (
                "import os,pathlib;"
                f"pathlib.Path({str(env_path)!r}).write_text("
                "os.environ.get('LLM_SUSPEND_ON_SERVER_ANOMALY','')+'|'+"
                "os.environ.get('LLM_SUSPEND_FAILURE_THRESHOLD','')+'|'+"
                "os.environ.get('LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS','')+'|'+"
                "os.environ.get('LLM_STREAM_IDLE_TIMEOUT_SECONDS',''),encoding='utf-8')"
            )
            plan_path.write_text(
                json.dumps(
                    {
                        "planned_runs": [
                            {
                                "post_id": 1,
                                "repeat_index": 1,
                                "output_json": "",
                                "command_argv": [sys.executable, "-c", code],
                            }
                        ]
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
            self.assertEqual(env_path.read_text(encoding="utf-8"), "0|0|45|45")

    def test_plan_and_run_env_overrides_are_forwarded_to_child_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_path = root / "env.txt"
            plan_path = root / "plan.json"
            code = (
                "import os,pathlib;"
                f"pathlib.Path({str(env_path)!r}).write_text("
                "os.environ.get('MCP_HEALTH_INCLUDE_SEARCH','')+'|'+"
                "os.environ.get('MCP_HEALTH_LIGHT_MODE','')+'|'+"
                "os.environ.get('MCP_HEALTH_REQUIRED_OK','')+'|'+"
                "os.environ.get('MCP_HEALTH_PROBE_BATCH_SIZE',''),encoding='utf-8')"
            )
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
                        "planned_runs": [
                            {
                                "post_id": 1,
                                "repeat_index": 1,
                                "output_json": "",
                                "env_overrides": {"MCP_HEALTH_PROBE_BATCH_SIZE": "16"},
                                "command_argv": [sys.executable, "-c", code],
                            }
                        ],
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
            plan_path = root / "plan.json"
            code = (
                "import os,pathlib,sys;"
                f"pathlib.Path({str(env_path)!r}).write_text("
                "os.environ.get('DASHBOARD_URL','')+'|'+"
                "os.environ.get('DASHBOARD_PORT','')+'|'+"
                "os.environ.get('EXPERT_DASHBOARD_FORWARD','')+'|'+"
                "str('--no-dashboard' in sys.argv),encoding='utf-8')"
            )
            plan_path.write_text(
                json.dumps(
                    {
                        "planned_runs": [
                            {
                                "post_id": 1,
                                "repeat_index": 1,
                                "output_json": "",
                                "command_argv": [sys.executable, "-c", code, "--no-dashboard"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

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
            self.assertEqual(env_path.read_text(encoding="utf-8"), "http://127.0.0.1:18080|18080|1|False")
            self.assertIn('"event": "dashboard_ready"', output.getvalue())
            self.assertIn('"dashboard_url": "http://127.0.0.1:18080"', output.getvalue())
            dashboard_marker = root / "logs" / "dashboard.marker.log"
            self.assertIn("status=already_running", dashboard_marker.read_text(encoding="utf-8"))

    def test_runner_starts_manifest_attach_for_dashboard_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = root / "plan.json"
            result_path = root / "result.json"
            manifest_path = root / "result_manifest.json"
            checkpoint_path = root / "result_checkpoint.jsonl"
            code = (
                "import json,pathlib,time;"
                f"result=pathlib.Path({str(result_path)!r});"
                f"manifest=pathlib.Path({str(manifest_path)!r});"
                f"checkpoint=pathlib.Path({str(checkpoint_path)!r});"
                "time.sleep(0.2);"
                "result.write_text('[]',encoding='utf-8');"
                "checkpoint.write_text('',encoding='utf-8');"
                "manifest.write_text(json.dumps({"
                "'run_id':'20260708_010203_000000',"
                "'input_post_count':1,"
                "'completed_count':1,"
                "'flushed_count':1,"
                "'pending_count':0,"
                "'failed_count':0,"
                "'large_run_complete':True,"
                "'parallel_count':16,"
                f"'output_file':{str(result_path)!r},"
                f"'checkpoint_jsonl':{str(checkpoint_path)!r}"
                "}),encoding='utf-8')"
            )
            plan_path.write_text(
                json.dumps(
                    {
                        "planned_runs": [
                            {
                                "post_id": 1,
                                "repeat_index": 1,
                                "output_json": str(result_path),
                                "manifest_json": str(manifest_path),
                                "command_argv": [sys.executable, "-c", code],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

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
            marker = root / "logs" / "result.marker.log"
            marker_text = marker.read_text(encoding="utf-8")
            self.assertIn("dashboard_attach_pid=", marker_text)
            self.assertIn(f"manifest={manifest_path}", marker_text)
            attach_log = root / "logs" / "result.dashboard_attach.log"
            self.assertIn("START_ATTACH", attach_log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
