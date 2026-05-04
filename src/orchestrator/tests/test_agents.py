import unittest
from unittest.mock import patch, MagicMock
from ..agents.gemini import GeminiAgentRunner
from ..agents.claude import ClaudeAgentRunner

class TestAgents(unittest.TestCase):
    def test_parse_json_result(self):
        # BaseCliAgentRunner is abstract, use GeminiAgentRunner to test the inherited method
        runner = GeminiAgentRunner()
        
        # Simple JSON
        self.assertEqual(runner._parse_json_result('{"a": 1}'), {"a": 1})
        
        # Markdown JSON
        raw = "Here is the result:\n```json\n{\"score\": 0.5}\n```\nDone."
        self.assertEqual(runner._parse_json_result(raw), {"score": 0.5})
        
        # Multiple JSONs, should pick the last one
        raw = '{"first": 1} ... some text ... {"last": 2}'
        self.assertEqual(runner._parse_json_result(raw), {"last": 2})
        
        # Malformed
        self.assertIsNone(runner._parse_json_result("not json"))

    @patch("orchestrator.agents.cli_base.register_process")
    @patch("orchestrator.agents.cli_base.unregister_process")
    @patch("subprocess.Popen")
    def test_gemini_runner(self, mock_popen, mock_unreg, mock_reg):
        # Mock Popen to simulate streaming output
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = [
            '{"type": "message", "role": "assistant", "content": "{\\"theory_id\\": \\"T1\\"}"}\n',
            '{"session_id": "sid_123"}\n',
            ""
        ]
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        runner = GeminiAgentRunner()
        data, session_id, error = runner.run(
            task_id="t1",
            prompt="p1",
            env_folder="/tmp",
            tx_id="tx_42"
        )
        
        self.assertIsNone(error)
        self.assertEqual(session_id, "sid_123")
        self.assertEqual(data, {"theory_id": "T1"})
        
        # Verify tx_id propagation
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
            ""
        ]
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        runner = ClaudeAgentRunner()
        data, session_id, error = runner.run(
            task_id="t1",
            prompt="p1",
            env_folder="/tmp",
            tx_id="tx_99"
        )
        
        self.assertIsNone(error)
        self.assertEqual(session_id, "sid_456")
        self.assertEqual(data, {"theory_id": "T2"})
        
        # Verify tx_id propagation
        args, kwargs = mock_popen.call_args
        env = kwargs["env"]
        self.assertEqual(env["CONTEXT_TRANSACTION_ID"], "tx_99")
