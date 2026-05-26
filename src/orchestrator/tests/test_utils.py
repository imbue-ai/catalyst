import unittest
from unittest.mock import patch, MagicMock
import subprocess
from ..utils import run_context_manager, get_ai_scientist_path
from ..models import Task

class TestUtils(unittest.TestCase):
    @patch("subprocess.run")
    def test_run_context_manager_success(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="T_123\n", 
            returncode=0
        )
        
        task = Task(
            id="t1",
            workflow_name="w1",
            framework="f1",
            env_folder="/tmp/env",
            workflow_inputs={}
        )
        
        args = ["store_results", "--some_flag"]
        result = run_context_manager(task, args)
        
        self.assertEqual(result, "T_123")
        
        # Verify call arguments
        mock_run.assert_called_once()
        called_args = mock_run.call_args[0][0]
        self.assertIn("uv", called_args)
        self.assertIn("python", called_args)
        self.assertIn("context_manager.py", called_args[3])
        self.assertIn("store_results", called_args)
        
        # Verify env
        kwargs = mock_run.call_args[1]
        self.assertIn("PATH", kwargs["env"])

    @patch("subprocess.run")
    def test_run_context_manager_failure(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr="error message")
        
        task = Task(
            id="t1",
            workflow_name="w1",
            framework="f1",
            env_folder="/tmp/env",
            workflow_inputs={}
        )
        
        with self.assertRaisesRegex(Exception, "Stderr:\nerror message"):
            run_context_manager(task, ["fail"])

    @patch("os.environ.get")
    @patch("os.path.exists")
    def test_get_ai_scientist_path_env_set(self, mock_exists, mock_get):
        mock_get.return_value = "/custom/path"
        result = get_ai_scientist_path()
        self.assertEqual(result, "/custom/path")

    @patch("os.environ.get")
    @patch("os.path.exists")
    def test_get_ai_scientist_path_catalyst_exists(self, mock_exists, mock_get):
        mock_get.return_value = None
        # Mocking exists: ~/.catalyst is evaluated first
        mock_exists.side_effect = lambda path: ".catalyst" in path
        
        result = get_ai_scientist_path()
        self.assertTrue(result.endswith(".catalyst"))

    @patch("os.environ.get")
    @patch("os.path.exists")
    def test_get_ai_scientist_path_legacy_only(self, mock_exists, mock_get):
        mock_get.return_value = None
        # Mocking exists: ~/.catalyst does not exist, but ~/.ai-scientist does
        mock_exists.side_effect = lambda path: ".ai-scientist" in path
        
        result = get_ai_scientist_path()
        self.assertTrue(result.endswith(".ai-scientist"))

    @patch("os.environ.get")
    @patch("os.path.exists")
    def test_get_ai_scientist_path_neither_exists(self, mock_exists, mock_get):
        mock_get.return_value = None
        mock_exists.return_value = False
        
        result = get_ai_scientist_path()
        self.assertTrue(result.endswith(".catalyst"))
