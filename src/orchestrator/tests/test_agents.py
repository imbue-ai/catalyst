"""Unit tests for the pure-logic parts of the agent runners.

End-to-end / real-mngr coverage lives in `src/scripts/smoke_test_mngr_runner.py`
(Stage B in the migration verification plan) and
`src/scripts/smoke_test_orchestrator.py` (Stage C). Those scripts spawn an
actual `mngr` agent against a real Claude turn and assert on the observed
labels, transcript, and step output. Anything in this file that would
require subprocess/network/timing to verify belongs in those scripts
instead.
"""

import unittest

from ..agents.mngr_claude import (
    _build_agent_args as _claude_build_agent_args,
    _extract_assistant_text as _claude_extract_assistant_text,
    _extract_status as _claude_extract_status,
)
from ..agents.mngr_gemini import (
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


