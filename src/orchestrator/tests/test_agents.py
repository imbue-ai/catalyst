"""Unit tests for the pure-logic parts of the agent runners and the
runner's fast-fail when an mngr agent type isn't registered.

End-to-end / real-mngr coverage lives in `src/scripts/smoke_test_mngr_runner.py`
(Stage B in the migration verification plan) and
`src/scripts/smoke_test_orchestrator.py` (Stage C). Those scripts spawn an
actual `mngr` agent against a real Claude turn and assert on the observed
labels, transcript, and step output. Anything in this file that would
require subprocess/network/timing to verify belongs in those scripts
instead.
"""

import unittest
from unittest.mock import MagicMock, patch

from ..agents.claude import ClaudeAgentRunner
from ..agents.gemini import GeminiAgentRunner
from ..agents.claude import (
    _build_agent_args as _claude_build_agent_args,
    _extract_assistant_text as _claude_extract_assistant_text,
    _extract_status as _claude_extract_status,
)
from ..agents.gemini import (
    _build_agent_args as _gemini_build_agent_args,
    _extract_assistant_text as _gemini_extract_assistant_text,
    _extract_status as _gemini_extract_status,
)
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


class TestGeminiAgentHelpers(unittest.TestCase):
    def test_build_agent_args_with_model(self):
        self.assertEqual(_gemini_build_agent_args("gemini-flash-x"), ["--model", "gemini-flash-x"])

    def test_build_agent_args_no_model(self):
        self.assertEqual(_gemini_build_agent_args(None), [])

    def test_extract_status_pulls_update_topic_summary(self):
        event = {
            "type": "assistant_message",
            "text": "",
            "tool_calls": [
                {
                    "tool_name": "update_topic",
                    "parameters": {"summary": "investigating phenomena"},
                }
            ],
        }
        self.assertEqual(_gemini_extract_status(event), "investigating phenomena")

    def test_extract_status_ignores_unrelated_tool_calls(self):
        event = {
            "type": "assistant_message",
            "text": "",
            "tool_calls": [{"tool_name": "ReadFile", "parameters": {"path": "/etc/passwd"}}],
        }
        self.assertIsNone(_gemini_extract_status(event))

    def test_extract_status_raises_on_unknown_update_topic_shape(self):
        # Tripwire: when mngr_gemini ships, if its update_topic shape
        # doesn't have a `parameters` dict we want to know loudly so we
        # can update the extractor instead of silently swallowing it.
        event = {
            "type": "assistant_message",
            "text": "",
            "tool_calls": [{"tool_name": "update_topic", "input_preview": "{...}"}],
        }
        with self.assertRaises(NotImplementedError):
            _gemini_extract_status(event)

    def test_extract_assistant_text_picks_text(self):
        self.assertEqual(
            _gemini_extract_assistant_text(
                {"type": "assistant_message", "text": "g hello"}
            ),
            "g hello",
        )


class TestAgentTypeRegistrationGuard(unittest.TestCase):
    """The runner pre-checks `mngr config get agent_types.<type>.command`
    before invoking `mngr create`. Without this guard, calling
    `mngr create --type <unregistered> -- ...args` constructs a tmux
    `send-keys -- ...` that fails with `command send-keys: invalid flag --`
    deep in the start path. Verify the runner returns a useful error
    when the type isn't registered, and proceeds normally when it is.
    """

    def _patch_config_get(self, registered: bool):
        result = MagicMock()
        result.returncode = 0 if registered else 1
        result.stdout = "claude\n" if registered else ""
        result.stderr = "" if registered else "Key not found: ...\n"
        return patch("orchestrator.agents.mngr_runner.subprocess.run", return_value=result)

    def test_gemini_fast_fails_with_invalid_type(self):
        runner = GeminiAgentRunner()
        with self._patch_config_get(registered=False):
            data, agent_name, error = runner.run(
                task_id="t1", prompt="p", env_folder="/tmp", stage="any",
            )
        self.assertIsNone(data)
        self.assertIsNone(agent_name)
        self.assertEqual(error, "invalid agent type: gemini")

    def test_claude_proceeds_when_registered(self):
        # We can't actually exercise the full happy path without mocking
        # every subprocess in the runner, which we explicitly stopped
        # doing. Instead, just verify the guard itself doesn't trip when
        # the type IS registered -- i.e. the helper returns None.
        runner = ClaudeAgentRunner()
        with self._patch_config_get(registered=True):
            self.assertIsNone(runner._agent_type_missing_message())
