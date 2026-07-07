import json
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools.run_independent_plan import run_plan


class RunIndependentPlanTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
