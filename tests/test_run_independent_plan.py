import json
import sys
import tempfile
import unittest
from pathlib import Path

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
            )

            self.assertEqual(rc, 0)
            self.assertEqual(env_path.read_text(encoding="utf-8"), "0|0|45|45")


if __name__ == "__main__":
    unittest.main()
