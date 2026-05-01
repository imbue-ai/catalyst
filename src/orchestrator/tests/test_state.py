import os
import json
from unittest.mock import patch, MagicMock
from .helpers import OrchestratorTestCase
from ..state import add_task, get_task, update_task, get_tasks, delete_task
from ..models import Task, TaskStatus

class TestState(OrchestratorTestCase):
    def test_create_and_get_task(self):
        task = Task(
            id="t1",
            workflow_name="w1",
            framework="f1",
            env_folder="e1",
            workflow_inputs={}
        )
        add_task(task)
        
        # Check retrieval
        retrieved = get_task("t1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.workflow_name, "w1")
        
        # Check all tasks
        all_tasks = get_tasks()
        self.assertEqual(len(all_tasks), 1)
        self.assertEqual(all_tasks[0].id, "t1")

    def test_update_task(self):
        task = Task(
            id="t1",
            workflow_name="w1",
            framework="f1",
            env_folder="e1",
            workflow_inputs={}
        )
        add_task(task)
        
        task.status = TaskStatus.RUNNING
        update_task(task)
        
        retrieved = get_task("t1")
        self.assertEqual(retrieved.status, TaskStatus.RUNNING)

    def test_persistence(self):
        task = Task(
            id="t1",
            workflow_name="w1",
            framework="f1",
            env_folder="e1",
            workflow_inputs={}
        )
        add_task(task)
        
        # Verify it's in the file
        with open(self.state_path, "r") as f:
            data = json.load(f)
            self.assertEqual(len(data["tasks"]), 1)
            self.assertEqual(data["tasks"][0]["id"], "t1")

    def test_delete_task(self):
        task = Task(
            id="t1",
            workflow_name="w1",
            framework="f1",
            env_folder="e1",
            workflow_inputs={}
        )
        add_task(task)
        self.assertEqual(len(get_tasks()), 1)
        
        delete_task("t1")
        self.assertEqual(len(get_tasks()), 0)

    @patch("os.killpg")
    @patch("os.getpgid")
    def test_cancel_task_process(self, mock_getpgid, mock_killpg):
        mock_process = MagicMock()
        mock_process.pid = 123
        mock_getpgid.return_value = 456
        
        from ..state import register_process, cancel_task_process
        register_process("t1", mock_process)
        
        cancel_task_process("t1")
        
        mock_killpg.assert_called_with(456, 15) # signal.SIGTERM is 15
        mock_process.wait.assert_called()
