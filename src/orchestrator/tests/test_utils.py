import unittest
from unittest.mock import patch, MagicMock
import subprocess
import os
from ..utils import run_context_manager
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
        
        # Verify env and cwd
        kwargs = mock_run.call_args[1]
        self.assertEqual(kwargs["cwd"], os.path.abspath("/tmp/env"))
        self.assertIn("PATH", kwargs["env"])

    @patch("subprocess.run")
    def test_run_context_manager_failure(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr="error")
        
        task = Task(
            id="t1",
            workflow_name="w1",
            framework="f1",
            env_folder="/tmp/env",
            workflow_inputs={}
        )
        
        with self.assertRaises(subprocess.CalledProcessError):
            run_context_manager(task, ["fail"])
