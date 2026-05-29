"""Unit tests for the pure-logic parts of the agent runners.

End-to-end / real-mngr coverage for the mngr-backed runners lives in
`src/scripts/smoke_test_mngr_runner.py` /
`src/scripts/smoke_test_antigravity_runner.py` (Stage B) and
`src/scripts/smoke_test_orchestrator.py` (Stage C). Those scripts spawn an
actual `mngr` agent against a real turn and assert on the observed labels,
transcript, and step output. Anything that would require subprocess / network
/ timing to verify for the mngr runners belongs in those scripts instead; the
direct (cli_base) runners are still covered with `subprocess.Popen` mocks here.
"""

import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from ..agents.claude import ClaudeAgentRunner
from ..agents.gemini import GeminiAgentRunner
from ..agents.mngr_antigravity import _build_agent_args as _antigravity_build_agent_args
from ..agents.mngr_antigravity import _extract_assistant_text as _antigravity_extract_assistant_text
from ..agents.mngr_antigravity import _extract_status as _antigravity_extract_status
from ..agents.mngr_claude import _build_agent_args as _claude_build_agent_args
from ..agents.mngr_claude import _extract_assistant_text as _claude_extract_assistant_text
from ..agents.mngr_claude import _extract_status as _claude_extract_status
from ..agents.mngr_runner import parse_json_result


class TestParseJsonResult(unittest.TestCase):
    def test_simple_json(self):
        self.assertEqual(parse_json_result('{"a": 1}'), {"a": 1})

    def test_markdown_json_block(self):
        raw = "Here is the result:\n```json\n{\"score\": 0.5}\n```\nDone."
        self.assertEqual(parse_json_result(raw), {"score": 0.5})

    def test_picks_last_json(self):
        raw = '{"first": 1} ... some text ... {"last": 2}'
        self.assertEqual(parse_json_result(raw), {"last": 2})

    def test_nested_json(self):
        raw = 'Random text before {"outer": {"inner": 42}, "other": "val"} text after'
        self.assertEqual(
            parse_json_result(raw), {"outer": {"inner": 42}, "other": "val"}
        )

    def test_multiple_nested(self):
        raw = '{"first": {"a": 1}} some noise {"last": {"b": 2}}'
        self.assertEqual(parse_json_result(raw), {"last": {"b": 2}})

    def test_malformed(self):
        self.assertIsNone(parse_json_result("not json"))


class TestClaudeAgentHelpers(unittest.TestCase):
    def test_build_agent_args_with_model(self):
        self.assertEqual(
            _claude_build_agent_args("claude-haiku-4-5-20251001"),
            ["--model", "claude-haiku-4-5-20251001"],
        )

    def test_build_agent_args_no_model(self):
        self.assertEqual(_claude_build_agent_args(None), [])

    def test_extract_assistant_text_picks_text(self):
        event = {"type": "assistant_message", "text": "hello world"}
        self.assertEqual(_claude_extract_assistant_text(event), "hello world")

    def test_extract_assistant_text_skips_empty(self):
        self.assertIsNone(_claude_extract_assistant_text(
            {"type": "assistant_message", "text": ""}
        ))

    def test_extract_assistant_text_skips_other_types(self):
        self.assertIsNone(_claude_extract_assistant_text(
            {"type": "tool_result", "text": "irrelevant"}
        ))

    def test_extract_status_collapses_whitespace(self):
        event = {"type": "assistant_message", "text": "two\n\n  newlines"}
        self.assertEqual(_claude_extract_status(event), "two newlines")


class TestAntigravityAgentHelpers(unittest.TestCase):
    def test_build_agent_args_ignores_model(self):
        # agy has no --model flag, so the runner contributes only --sandbox
        # regardless of the requested model.
        self.assertEqual(_antigravity_build_agent_args("some-model"), ["--sandbox"])
        self.assertEqual(_antigravity_build_agent_args(None), ["--sandbox"])

    def test_extract_assistant_text_picks_text(self):
        self.assertEqual(
            _antigravity_extract_assistant_text(
                {"type": "assistant_message", "text": '{"created": true}'}
            ),
            '{"created": true}',
        )

    def test_extract_assistant_text_skips_empty(self):
        # The tool-calling PLANNER_RESPONSE carries empty text; it must not
        # contribute to the harvested final result.
        self.assertIsNone(
            _antigravity_extract_assistant_text(
                {"type": "assistant_message", "text": "", "tool_calls": [{"tool_name": "run_command"}]}
            )
        )

    def test_extract_status_collapses_text(self):
        event = {"type": "assistant_message", "text": "two\n\n  newlines", "tool_calls": []}
        self.assertEqual(_antigravity_extract_status(event), "two newlines")

    def test_extract_status_names_tool_when_text_empty(self):
        # A tool-using step has empty text but a requested tool; surface the
        # tool name so the dashboard shows live progress.
        event = {
            "type": "assistant_message",
            "text": "",
            "tool_calls": [{"tool_name": "run_command", "input_preview": "{...}"}],
        }
        self.assertEqual(_antigravity_extract_status(event), "Running run_command")

    def test_extract_status_ignores_non_assistant_events(self):
        self.assertIsNone(
            _antigravity_extract_status({"type": "user_message", "content": "hi"})
        )


class TestDirectRunners(unittest.TestCase):
    """Covers the direct (cli_base) `gemini` / `claude` / `agy` runners via
    `subprocess.Popen` mocks."""

    def test_parse_json_result(self):
        # BaseCliAgentRunner is abstract; use GeminiAgentRunner to test the
        # inherited helper.
        runner = GeminiAgentRunner()
        self.assertEqual(runner._parse_json_result('{"a": 1}'), {"a": 1})
        raw = "Here is the result:\n```json\n{\"score\": 0.5}\n```\nDone."
        self.assertEqual(runner._parse_json_result(raw), {"score": 0.5})
        raw = '{"first": 1} ... some text ... {"last": 2}'
        self.assertEqual(runner._parse_json_result(raw), {"last": 2})
        raw = 'Random text before {"outer": {"inner": 42}, "other": "val"} text after'
        self.assertEqual(runner._parse_json_result(raw), {"outer": {"inner": 42}, "other": "val"})
        raw = '{"first": {"a": 1}} some noise {"last": {"b": 2}}'
        self.assertEqual(runner._parse_json_result(raw), {"last": {"b": 2}})
        self.assertIsNone(runner._parse_json_result("not json"))

    @patch("orchestrator.agents.cli_base.register_process")
    @patch("orchestrator.agents.cli_base.unregister_process")
    @patch("subprocess.Popen")
    def test_gemini_runner(self, mock_popen, mock_unreg, mock_reg):
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = [
            '{"type": "message", "role": "assistant", "content": "{\\"theory_id\\": \\"T1\\"}"}\n',
            '{"session_id": "sid_123"}\n',
            "",
        ]
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        runner = GeminiAgentRunner()
        data, session_id, error = runner.run(
            task_id="t1",
            prompt="p1",
            env_folder="/tmp",
            tx_id="tx_42",
        )

        self.assertIsNone(error)
        self.assertEqual(session_id, "sid_123")
        self.assertEqual(data, {"theory_id": "T1"})
        args, kwargs = mock_popen.call_args
        env = kwargs["env"]
        self.assertEqual(env["CONTEXT_TRANSACTION_ID"], "tx_42")

    @patch("orchestrator.agents.cli_base.register_process")
    @patch("orchestrator.agents.cli_base.unregister_process")
    @patch("subprocess.Popen")
    def test_claude_runner(self, mock_popen, mock_unreg, mock_reg):
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = [
            '{"type": "result", "result": "{\\"theory_id\\": \\"T2\\"}"}\n',
            '{"session_id": "sid_456"}\n',
            "",
        ]
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        runner = ClaudeAgentRunner()
        data, session_id, error = runner.run(
            task_id="t1",
            prompt="p1",
            env_folder="/tmp",
            tx_id="tx_99",
        )

        self.assertIsNone(error)
        self.assertEqual(session_id, "sid_456")
        self.assertEqual(data, {"theory_id": "T2"})
        args, kwargs = mock_popen.call_args
        env = kwargs["env"]
        self.assertEqual(env["CONTEXT_TRANSACTION_ID"], "tx_99")

    @patch("orchestrator.agents.cli_base.register_process")
    @patch("orchestrator.agents.cli_base.unregister_process")
    @patch("subprocess.Popen")
    def test_agy_runner(self, mock_popen, mock_unreg, mock_reg):
        from ..agents.agy import AgyAgentRunner

        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            "Random setup output...\n```json\n{\"theory_id\": \"T3\"}\n```\n",
            None,
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        runner = AgyAgentRunner()
        data, session_id, error = runner.run(
            task_id="t1",
            prompt="p1",
            env_folder="/tmp",
            tx_id="tx_101",
            model="ignored-model",
        )

        self.assertIsNone(error)
        self.assertIsNone(session_id)
        self.assertEqual(data, {"theory_id": "T3"})
        args, kwargs = mock_popen.call_args
        env = kwargs["env"]
        self.assertEqual(env["CONTEXT_TRANSACTION_ID"], "tx_101")
        cmd = args[0]
        self.assertIn("agy", cmd)
        self.assertIn("--sandbox", cmd)
        self.assertIn("--print-timeout", cmd)
        self.assertIn("6h", cmd)
        self.assertNotIn("ignored-model", cmd)
        self.assertNotIn("--model", cmd)
