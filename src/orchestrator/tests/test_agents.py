import json
import unittest
from unittest.mock import MagicMock, patch

from ..agents.claude import ClaudeAgentRunner
from ..agents.gemini import GeminiAgentRunner
from ..agents.mngr_runner import parse_json_result


def _build_event_lines(events):
    return [json.dumps(e) + "\n" for e in events]


def _make_event_proc(event_lines):
    """Create a mock subprocess.Popen for `mngr event --follow`."""
    proc = MagicMock()
    proc.stdout = iter(event_lines)
    proc.terminate.return_value = None
    proc.wait.return_value = 0
    proc.kill.return_value = None
    return proc


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


class _RunnerTestBase(unittest.TestCase):
    """Common scaffolding: mock `mngr create`, `mngr event`, `mngr wait`, `mngr stop`."""

    def _patch_subprocess(self, event_lines, wait_returncode=0):
        # Create the mocks; tests call _start_patches() to enter them.
        self._event_proc = _make_event_proc(event_lines)

        def fake_run(cmd, **kwargs):
            result = MagicMock()
            result.stdout = ""
            result.stderr = ""
            if cmd[:2] == ["mngr", "create"]:
                self._create_calls.append(cmd)
                result.returncode = 0
            elif cmd[:2] == ["mngr", "wait"]:
                self._wait_calls.append(cmd)
                result.returncode = wait_returncode
            elif cmd[:2] == ["mngr", "stop"]:
                self._stop_calls.append(cmd)
                result.returncode = 0
            else:
                result.returncode = 0
            return result

        def fake_popen(cmd, **kwargs):
            self._popen_calls.append(cmd)
            assert cmd[:2] == ["mngr", "event"]
            return self._event_proc

        self._create_calls = []
        self._wait_calls = []
        self._stop_calls = []
        self._popen_calls = []

        run_patcher = patch("subprocess.run", side_effect=fake_run)
        popen_patcher = patch("subprocess.Popen", side_effect=fake_popen)
        run_patcher.start()
        popen_patcher.start()
        self.addCleanup(run_patcher.stop)
        self.addCleanup(popen_patcher.stop)

    def _assert_create_has_label(self, key, value):
        cmd = self._create_calls[0]
        # labels are passed as `--label key=value` pairs
        labels = []
        for i, arg in enumerate(cmd):
            if arg == "--label" and i + 1 < len(cmd):
                labels.append(cmd[i + 1])
        self.assertIn(f"{key}={value}", labels)

    def _assert_create_has_env(self, key, value):
        cmd = self._create_calls[0]
        envs = []
        for i, arg in enumerate(cmd):
            if arg == "--env" and i + 1 < len(cmd):
                envs.append(cmd[i + 1])
        self.assertIn(f"{key}={value}", envs)

    def _assert_no_destroy_called(self):
        for cmd in self._create_calls + self._wait_calls + self._stop_calls:
            self.assertNotEqual(
                cmd[1] if len(cmd) > 1 else "", "destroy",
                f"mngr destroy was called: {cmd}",
            )


class TestClaudeAgentRunner(_RunnerTestBase):
    def test_happy_path(self):
        events = [
            {
                "type": "assistant_message",
                "source": "claude/common_transcript",
                "text": "Working on theory T1",
            },
            {
                "type": "assistant_message",
                "source": "claude/common_transcript",
                "text": '{"theory_id": "T1"}',
            },
        ]
        self._patch_subprocess(_build_event_lines(events))

        statuses = []
        runner = ClaudeAgentRunner()
        data, agent_name, error = runner.run(
            task_id="task_abcdef12345678",
            prompt="please make a theory",
            env_folder="/tmp/scientist-env",
            model="claude-haiku-4-5-20251001",
            tx_id="tx_42",
            stage="write-theory",
            on_status=statuses.append,
        )

        self.assertIsNone(error)
        self.assertIsNotNone(agent_name)
        self.assertTrue(agent_name.startswith("aisci-"))
        self.assertEqual(data, {"theory_id": "T1"})
        self.assertTrue(any("Working on theory T1" in s for s in statuses))

        # mngr create was invoked with the expected shape
        self.assertEqual(len(self._create_calls), 1)
        cmd = self._create_calls[0]
        self.assertEqual(cmd[:3], ["mngr", "create", agent_name])
        self.assertIn("--type", cmd)
        self.assertEqual(cmd[cmd.index("--type") + 1], "claude")
        self.assertIn("--no-connect", cmd)
        self.assertIn("--message-file", cmd)
        self.assertIn("--from", cmd)
        self.assertEqual(cmd[cmd.index("--from") + 1], ":/tmp/scientist-env")
        self.assertIn("--transfer", cmd)
        self.assertEqual(cmd[cmd.index("--transfer") + 1], "none")

        # All four labels and env vars
        self._assert_create_has_label("app", "ai-scientist")
        self._assert_create_has_label("ai-scientist-task", "task_abcdef12345678")
        self._assert_create_has_label("ai-scientist-stage", "write-theory")
        self._assert_create_has_label("ai-scientist-framework", "claude")
        self._assert_create_has_env("CONTEXT_TRANSACTION_ID", "tx_42")
        self._assert_create_has_env(
            "AI_SCIENTIST_DB_PATH", "/tmp/scientist-env/.ai-scientist-db"
        )

        # Trailing claude args after `--`
        sep_idx = cmd.index("--")
        trailing = cmd[sep_idx + 1 :]
        self.assertIn("--dangerously-skip-permissions", trailing)
        self.assertIn("--verbose", trailing)
        self.assertIn("--append-system-prompt", trailing)
        self.assertIn("--model", trailing)
        self.assertEqual(trailing[trailing.index("--model") + 1], "claude-haiku-4-5-20251001")

        # Event follower spawned
        self.assertEqual(len(self._popen_calls), 1)
        ev_cmd = self._popen_calls[0]
        self.assertEqual(ev_cmd[:3], ["mngr", "event", agent_name])
        self.assertIn("--follow", ev_cmd)
        self.assertIn("--format", ev_cmd)
        self.assertEqual(ev_cmd[ev_cmd.index("--format") + 1], "jsonl")

        # mngr wait with the right states
        self.assertEqual(len(self._wait_calls), 1)
        wait_cmd = self._wait_calls[0]
        states = [wait_cmd[i + 1] for i, arg in enumerate(wait_cmd) if arg == "--state"]
        self.assertIn("WAITING", states)
        self.assertIn("DONE", states)
        self.assertIn("STOPPED", states)

        # mngr stop called, mngr destroy never called
        self.assertEqual(len(self._stop_calls), 1)
        self.assertEqual(self._stop_calls[0][:3], ["mngr", "stop", agent_name])
        self._assert_no_destroy_called()

    def test_unparseable_returns_error(self):
        events = [
            {
                "type": "assistant_message",
                "source": "claude/common_transcript",
                "text": "I cannot produce JSON, sorry.",
            },
        ]
        self._patch_subprocess(_build_event_lines(events))

        runner = ClaudeAgentRunner()
        data, agent_name, error = runner.run(
            task_id="t1",
            prompt="p",
            env_folder="/tmp",
            stage="any",
        )
        self.assertIsNone(data)
        self.assertIsNotNone(agent_name)
        self.assertIn("Could not parse JSON", error)


class TestGeminiAgentRunner(_RunnerTestBase):
    def test_happy_path_with_update_topic(self):
        events = [
            {
                "type": "assistant_message",
                "source": "claude/common_transcript",
                "text": "",
                "tool_calls": [
                    {
                        "tool_name": "update_topic",
                        "parameters": {"summary": "Investigating phenomena"},
                    }
                ],
            },
            {
                "type": "assistant_message",
                "source": "claude/common_transcript",
                "text": '{"theory_id": "T2"}',
            },
        ]
        self._patch_subprocess(_build_event_lines(events))

        statuses = []
        runner = GeminiAgentRunner()
        data, agent_name, error = runner.run(
            task_id="task_xyz_99999999",
            prompt="hello gemini",
            env_folder="/tmp/gem-env",
            tx_id="tx_99",
            stage="explore",
            on_status=statuses.append,
        )

        self.assertIsNone(error)
        self.assertEqual(data, {"theory_id": "T2"})
        self.assertIn("Investigating phenomena", statuses)

        cmd = self._create_calls[0]
        self.assertEqual(cmd[cmd.index("--type") + 1], "gemini")
        self._assert_create_has_label("ai-scientist-framework", "gemini")
        self._assert_create_has_env("CONTEXT_TRANSACTION_ID", "tx_99")
        self._assert_no_destroy_called()


class TestWaitTimeout(_RunnerTestBase):
    def test_wait_timeout_returns_error(self):
        self._patch_subprocess(_build_event_lines([]), wait_returncode=2)

        runner = ClaudeAgentRunner()
        data, agent_name, error = runner.run(
            task_id="t1",
            prompt="p",
            env_folder="/tmp",
            stage="any",
        )
        self.assertIsNone(data)
        self.assertIsNotNone(agent_name)
        self.assertIn("did not reach", error)
        # We still try to stop the agent so it doesn't hang forever.
        self.assertEqual(len(self._stop_calls), 1)
