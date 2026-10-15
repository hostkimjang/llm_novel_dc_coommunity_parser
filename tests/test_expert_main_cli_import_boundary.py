"""expert_main import와 직접 실행의 CLI 인자 경계를 검증한다."""

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExpertMainCliImportBoundaryTests(unittest.TestCase):
    def run_python(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-B", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def test_unittest_discover_arguments_do_not_break_fresh_import(self) -> None:
        result = self.run_python(
            "-c",
            "import sys; "
            "sys.argv = ['unittest', 'discover', '-s', 'tests']; "
            "import expert_main; "
            "assert sys.argv == ['unittest', 'discover', '-s', 'tests']; "
            "assert expert_main._CLI_ARGS.server_type is None; "
            "assert expert_main._CLI_ARGS.input is None; "
            "print('IMPORTED')",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "IMPORTED")

    def test_callers_help_and_dashboard_flags_do_not_change_import(self) -> None:
        result = self.run_python(
            "-c",
            "import sys; "
            "sys.argv = ['caller', '--help', '--no-dashboard']; "
            "import expert_main; "
            "assert expert_main._CLI_ARGS.no_dashboard is False; "
            "assert expert_main._NO_DASHBOARD is False; "
            "print('IMPORTED')",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "IMPORTED")
        self.assertEqual(result.stderr, "")

    def test_explicit_parser_keeps_cli_options_and_input_priority(self) -> None:
        result = self.run_python(
            "-c",
            "import sys, expert_main; "
            "sys.argv = ['expert_main.py', '-s', 'vllm', '--parallel', '16', "
            "'positional.jsonl', '--input', 'flag.jsonl', '--no-dashboard']; "
            "args = expert_main._parse_args(); "
            "assert args.server_type == 'vllm'; "
            "assert args.parallel == 16; "
            "assert args.input == 'flag.jsonl'; "
            "assert args.no_dashboard is True; "
            "print('PARSED')",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "PARSED")

    def test_direct_cli_help_remains_available(self) -> None:
        result = self.run_python("expert_main.py", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--server-type", result.stderr)
        self.assertIn("--input", result.stderr)
        self.assertIn("--no-dashboard", result.stderr)


if __name__ == "__main__":
    unittest.main()
