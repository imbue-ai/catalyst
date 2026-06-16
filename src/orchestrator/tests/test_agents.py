import time
import unittest
from unittest.mock import patch, MagicMock
from ..agents.base import parse_json_result
from ..agents.gemini import GeminiAgentRunner
from ..agents.claude import ClaudeAgentRunner
from ..agents.agy import AgyAgentRunner
from ..agents.mngr_runner import extract_assistant_text, extract_status, MngrAgentRunner
from ..models import TheoryScoringWeights
from pydantic import ValidationError


class TestAgents(unittest.TestCase):
    def test_parse_json_result(self):
        # Simple JSON
        self.assertEqual(parse_json_result('{"a": 1}'), {"a": 1})

        # Markdown JSON
        raw = 'Here is the result:\n```json\n{"score": 0.5}\n```\nDone.'
        self.assertEqual(parse_json_result(raw), {"score": 0.5})

        # Multiple JSONs, should pick the last one
        raw = '{"first": 1} ... some text ... {"last": 2}'
        self.assertEqual(parse_json_result(raw), {"last": 2})

        # Nested JSON, should correctly find the outer boundaries
        raw = 'Random text before {"outer": {"inner": 42}, "other": "val"} text after'
        self.assertEqual(
            parse_json_result(raw), {"outer": {"inner": 42}, "other": "val"}
        )

        # Multiple JSONs with nesting
        raw = '{"first": {"a": 1}} some noise {"last": {"b": 2}}'
        self.assertEqual(parse_json_result(raw), {"last": {"b": 2}})

        # Malformed
        self.assertIsNone(parse_json_result("not json"))

    @patch("orchestrator.agents.cli_base.register_cancellable")
    @patch("orchestrator.agents.cli_base.unregister_cancellable")
    @patch("subprocess.Popen")
    def test_gemini_runner(self, mock_popen, mock_unreg, mock_reg):
        # Mock Popen to simulate streaming output
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
        common_env = runner.build_common_environment_variables(
            env_folder="/tmp",
            tx_id="tx_42",
        )
        data, session_id, error = runner.run(
            task_id="t1",
            prompt="p1",
            env_folder="/tmp",
            stage="t1-stage",
            common_environment_variables=common_env,
        )

        self.assertIsNone(error)
        self.assertEqual(session_id, "sid_123")
        self.assertEqual(data, {"theory_id": "T1"})

        # Verify tx_id propagation
        args, kwargs = mock_popen.call_args
        env = kwargs["env"]
        self.assertEqual(env["CONTEXT_TRANSACTION_ID"], "tx_42")

    @patch("orchestrator.agents.cli_base.register_cancellable")
    @patch("orchestrator.agents.cli_base.unregister_cancellable")
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
        common_env = runner.build_common_environment_variables(
            env_folder="/tmp",
            tx_id="tx_99",
        )
        data, session_id, error = runner.run(
            task_id="t1",
            prompt="p1",
            env_folder="/tmp",
            stage="t1-stage",
            common_environment_variables=common_env,
        )

        self.assertIsNone(error)
        self.assertEqual(session_id, "sid_456")
        self.assertEqual(data, {"theory_id": "T2"})

        # Verify tx_id propagation
        args, kwargs = mock_popen.call_args
        env = kwargs["env"]
        self.assertEqual(env["CONTEXT_TRANSACTION_ID"], "tx_99")

    @patch("orchestrator.agents.cli_base.register_cancellable")
    @patch("orchestrator.agents.cli_base.unregister_cancellable")
    @patch("subprocess.Popen")
    def test_agy_runner(self, mock_popen, mock_unreg, mock_reg):


        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            'Random setup output...\n```json\n{"theory_id": "T3"}\n```\n',
            None,
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        runner = AgyAgentRunner()
        common_env = runner.build_common_environment_variables(
            env_folder="/tmp",
            tx_id="tx_101",
        )
        data, session_id, error = runner.run(
            task_id="t1",
            prompt="p1",
            env_folder="/tmp",
            stage="t1-stage",
            common_environment_variables=common_env,
            model="Gemini 3.5 Flash (Low)",
        )

        self.assertIsNone(error)
        self.assertIsNone(session_id)
        self.assertEqual(data, {"theory_id": "T3"})

        # Verify tx_id propagation
        args, kwargs = mock_popen.call_args
        env = kwargs["env"]
        self.assertEqual(env["CONTEXT_TRANSACTION_ID"], "tx_101")

        # Verify command flags, including --model. Model name matches
        # agy's in-session `/model` menu; passed through as a single
        # argv element so spaces / parens survive without shell-quoting
        # concerns.
        cmd = args[0]
        self.assertIn("agy", cmd)
        # Sandboxing is currently disabled for Antigravity CLI. Re-enable eventually.
        self.assertNotIn("--sandbox", cmd)
        self.assertIn("--print-timeout", cmd)
        self.assertIn("--model", cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "Gemini 3.5 Flash (Low)")
        # --model lives before -p so the prompt remains the last arg.
        self.assertLess(cmd.index("--model"), cmd.index("-p"))


class TestSharedExtractors(unittest.TestCase):
    """Covers `extract_assistant_text` and `extract_status` in mngr_runner.
    Shared by mngr_claude + mngr_antigravity since both plugins' common
    transcripts normalize to the same `assistant_message` shape."""

    def test_extract_assistant_text_picks_text(self):
        self.assertEqual(
            extract_assistant_text({"type": "assistant_message", "text": "hello"}),
            "hello",
        )

    def test_extract_assistant_text_skips_empty(self):
        self.assertIsNone(
            extract_assistant_text({"type": "assistant_message", "text": ""})
        )

    def test_extract_assistant_text_skips_other_types(self):
        self.assertIsNone(
            extract_assistant_text({"type": "tool_result", "text": "irrelevant"})
        )

    def test_extract_status_collapses_whitespace(self):
        event = {"type": "assistant_message", "text": "two\n\n  newlines"}
        self.assertEqual(extract_status(event), "two newlines")

    def test_extract_status_falls_back_to_tool_name(self):
        # A tool-using step has empty text but a requested tool; surface the
        # tool name so the dashboard shows live progress. Applies to both
        # agy's PLANNER_RESPONSE-for-tool and claude's assistant_message
        # when it calls a tool with no preamble text.
        event = {
            "type": "assistant_message",
            "text": "",
            "tool_calls": [{"tool_name": "run_command", "input_preview": "{...}"}],
        }
        self.assertEqual(extract_status(event), "Running run_command")

    def test_extract_status_ignores_non_assistant_events(self):
        self.assertIsNone(extract_status({"type": "user_message", "content": "hi"}))


class TestMngrAgentRunner(unittest.TestCase):
    def _assert_waiting_turn_end(
        self, mock_popen, transcript_source: str, assistant_text: str
    ) -> None:
        """Drive `_wait_for_turn_end` through a clean turn end: the WAITING
        watcher exits 0 (the active marker was cleared by the plugin's Stop
        hook), and the last assistant_message on the agent's transcript
        source is harvested from the event stream."""
        runner = MngrAgentRunner(
            agent_type="agent",
            framework="mngr-agent",
            transcript_source=transcript_source,
        )

        mock_event_proc = MagicMock()
        mock_event_proc.stdout = [
            '{"source": "%s", "type": "assistant_message", "text": "%s"}\n'
            % (transcript_source, assistant_text.replace('"', '\\"')),
        ]

        # WAITING exits 0 (turn ended); STOPPED never fires (would-be external
        # pause). Whichever `mngr wait` we get is keyed off the requested state.
        mock_wait_proc = MagicMock()
        mock_wait_proc.wait.return_value = 0
        mock_stop_proc = MagicMock()
        mock_stop_proc.wait.return_value = 1

        def popen_side_effect(cmd, *args, **kwargs):
            if "event" in cmd:
                return mock_event_proc
            elif "wait" in cmd:
                return mock_wait_proc if "WAITING" in cmd else mock_stop_proc
            return MagicMock()

        mock_popen.side_effect = popen_side_effect

        # The agent is WAITING throughout the harvest; the parseable text is
        # picked up on the first poll.
        with patch.object(runner, "_poll_lifecycle_state", return_value="WAITING"):
            saw_turn_end, harvested = runner._wait_for_turn_end("agent-123", None)
        self.assertTrue(saw_turn_end)
        self.assertEqual(harvested, assistant_text)

    # Patch out the post-turn-end grace sleep so the test doesn't block on it.
    @patch("orchestrator.agents.mngr_runner.time.sleep")
    @patch("subprocess.Popen")
    def test_wait_for_turn_end_claude_waiting_state(self, mock_popen, _mock_sleep):
        self._assert_waiting_turn_end(
            mock_popen, "claude/common_transcript", '{"score": 0.9}'
        )

    # Shrink the post-turn-end grace budget so the timeout path runs fast in tests.
    @patch("orchestrator.agents.mngr_runner._POST_TURN_END_GRACE_SECONDS", 0.1)
    @patch("orchestrator.agents.mngr_runner.time.sleep")
    @patch("subprocess.Popen")
    def test_wait_for_turn_end_json_grace_times_out_on_non_json(
        self, mock_popen, _mock_sleep
    ):
        """When the agent stays WAITING but the harvested text never parses as
        JSON (and it never resumes), the continuous-WAITING grace runs to its
        deadline and returns the unparseable text -- it must not hang. This is
        the 'genuinely ended early on non-JSON' path of the turn-end-grace."""
        runner = MngrAgentRunner(
            agent_type="agent",
            framework="mngr-agent",
            transcript_source="claude/common_transcript",
        )
        preamble = "I'll spawn 5 agents and wait for them to report back."
        mock_event_proc = MagicMock()
        mock_event_proc.stdout = [
            '{"source": "claude/common_transcript", "type": "assistant_message", "text": "%s"}\n'
            % preamble,
        ]
        mock_wait_proc = MagicMock()
        mock_wait_proc.wait.return_value = 0
        mock_stop_proc = MagicMock()
        mock_stop_proc.wait.return_value = 1

        def popen_side_effect(cmd, *args, **kwargs):
            if "event" in cmd:
                return mock_event_proc
            elif "wait" in cmd:
                return mock_wait_proc if "WAITING" in cmd else mock_stop_proc
            return MagicMock()

        mock_popen.side_effect = popen_side_effect

        # Agent stays continuously WAITING -> the grace times out.
        with patch.object(runner, "_poll_lifecycle_state", return_value="WAITING"):
            saw_turn_end, harvested = runner._wait_for_turn_end("agent-123", None)
        self.assertTrue(saw_turn_end)
        # Non-JSON text is still returned (so _wait_and_harvest can surface the
        # "could not parse" error); the grace loop just didn't recover a better one.
        self.assertEqual(harvested, preamble)

    @patch("orchestrator.agents.mngr_runner.time.sleep")
    def test_await_final_message_waits_through_resume(self, _mock_sleep):
        """A premature/intermediate WAITING that resumes to RUNNING must NOT end
        the harvest on the preamble: we re-arm on the next WAITING and return the
        real (parseable) message, however long the continuation takes."""
        runner = MngrAgentRunner(
            agent_type="agent",
            framework="mngr-agent",
            transcript_source="claude/common_transcript",
        )
        state = {"last_assistant_text": "I'll spawn 5 agents and wait."}
        json_text = '{"score": 0.9}'

        def block_side_effect(agent_name, deadline):
            # By the time the agent returns to WAITING, its real final message
            # (JSON) has landed in the transcript.
            state["last_assistant_text"] = json_text
            return True

        with patch.object(
            runner, "_poll_lifecycle_state", side_effect=["WAITING", "RUNNING", "WAITING"]
        ), patch.object(
            runner, "_block_until_waiting", side_effect=block_side_effect
        ) as mock_block:
            runner._await_final_message("agent-123", state, time.monotonic() + 100)

        mock_block.assert_called_once()  # detected the resume and re-armed
        self.assertEqual(state["last_assistant_text"], json_text)

    @patch("orchestrator.agents.mngr_runner.time.sleep")
    def test_await_final_message_stops_on_terminal_state(self, _mock_sleep):
        """A terminal state (e.g. STOPPED from an external pause) ends the wait
        immediately -- we do not sit out the grace or try to re-arm."""
        runner = MngrAgentRunner(
            agent_type="agent",
            framework="mngr-agent",
            transcript_source="claude/common_transcript",
        )
        state = {"last_assistant_text": "I'll spawn 5 agents and wait."}
        with patch.object(
            runner, "_poll_lifecycle_state", return_value="STOPPED"
        ), patch.object(runner, "_block_until_waiting") as mock_block:
            runner._await_final_message("agent-123", state, time.monotonic() + 100)
        mock_block.assert_not_called()
        self.assertEqual(state["last_assistant_text"], "I'll spawn 5 agents and wait.")

    @patch("orchestrator.agents.mngr_runner.time.sleep")
    def test_await_final_message_returns_on_parse_while_waiting(self, _mock_sleep):
        """The common case: WAITING with parseable text returns on the first
        poll, without re-arming."""
        runner = MngrAgentRunner(
            agent_type="agent",
            framework="mngr-agent",
            transcript_source="claude/common_transcript",
        )
        state = {"last_assistant_text": '{"score": 0.9}'}
        with patch.object(
            runner, "_poll_lifecycle_state", return_value="WAITING"
        ) as mock_poll, patch.object(runner, "_block_until_waiting") as mock_block:
            runner._await_final_message("agent-123", state, time.monotonic() + 100)
        mock_block.assert_not_called()
        mock_poll.assert_called_once()

    def test_block_until_waiting_true_when_waiting(self):
        """`_block_until_waiting` reports True iff the agent is WAITING once the
        `mngr wait` (WAITING-or-STOPPED) call resolves successfully."""
        runner = MngrAgentRunner(
            agent_type="agent",
            framework="mngr-agent",
            transcript_source="claude/common_transcript",
        )
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        with patch("subprocess.Popen", return_value=mock_proc), patch.object(
            runner, "_poll_lifecycle_state", return_value="WAITING"
        ), patch.object(runner, "_terminate_proc"):
            self.assertTrue(runner._block_until_waiting("agent-123", time.monotonic() + 100))

    def test_block_until_waiting_false_on_stop(self):
        """If the re-arm resolves on STOPPED (external pause) rather than WAITING,
        `_block_until_waiting` returns False so the caller stops waiting."""
        runner = MngrAgentRunner(
            agent_type="agent",
            framework="mngr-agent",
            transcript_source="claude/common_transcript",
        )
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        with patch("subprocess.Popen", return_value=mock_proc), patch.object(
            runner, "_poll_lifecycle_state", return_value="STOPPED"
        ), patch.object(runner, "_terminate_proc"):
            self.assertFalse(runner._block_until_waiting("agent-123", time.monotonic() + 100))

    @patch("orchestrator.agents.mngr_runner.time.sleep")
    @patch("subprocess.Popen")
    def test_wait_for_turn_end_antigravity_waiting_state(self, mock_popen, _mock_sleep):
        self._assert_waiting_turn_end(
            mock_popen, "antigravity/common_transcript", '{"score": 0.8}'
        )

    def test_theory_scoring_weights_propagation(self):


        runner = ClaudeAgentRunner()
        weights = TheoryScoringWeights(
            correctness_weight=0.1,
            power_weight=0.5,
            adherence_weight=0.9,
        )
        common_env = runner.build_common_environment_variables(
            env_folder="/tmp",
            tx_id="tx_123",
            theory_scoring_weights=weights,
        )
        self.assertEqual(common_env["CONTEXT_TRANSACTION_ID"], "tx_123")
        self.assertEqual(common_env["CATALYST_SCORING_CORRECTNESS_WEIGHT"], "0.1")
        self.assertEqual(common_env["CATALYST_SCORING_POWER_WEIGHT"], "0.5")
        self.assertEqual(common_env["CATALYST_SCORING_ADHERENCE_WEIGHT"], "0.9")

        # Verify validation bounds ge=0.0, le=1.0
        with self.assertRaises(ValidationError):
            TheoryScoringWeights(
                correctness_weight=1.5,
                power_weight=0.5,
                adherence_weight=0.9,
            )

        with self.assertRaises(ValidationError):
            TheoryScoringWeights(
                correctness_weight=-0.1,
                power_weight=0.5,
                adherence_weight=0.9,
            )
