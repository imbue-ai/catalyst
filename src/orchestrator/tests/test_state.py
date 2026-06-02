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

    @patch("subprocess.run")
    def test_cancel_task_process_stops_each_agent(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        from ..state import register_agent, cancel_task_process
        register_agent("t1", "cata-t1-stage-aaa")
        register_agent("t1", "cata-t1-stage-bbb")

        cancel_task_process("t1")

        called_cmds = [call.args[0] for call in mock_run.call_args_list]
        self.assertEqual(len(called_cmds), 2)
        for cmd in called_cmds:
            self.assertEqual(cmd[:2], ["mngr", "stop"])
        stopped_names = sorted(cmd[2] for cmd in called_cmds)
        self.assertEqual(stopped_names, ["cata-t1-stage-aaa", "cata-t1-stage-bbb"])

    def test_cancel_task_process_no_agents(self):
        # No registered work for `task_id` -> no-op, doesn't even subprocess.
        from ..state import cancel_task_process
        with patch("subprocess.run") as mock_run:
            cancel_task_process("never-registered")
            mock_run.assert_not_called()

    def test_unregister_agent(self):
        from ..state import register_agent, unregister_agent, cancel_task_process
        register_agent("t1", "agent-a")
        register_agent("t1", "agent-b")
        unregister_agent("t1", "agent-a")

        # Cancel after unregister: only the remaining one gets stopped.
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cancel_task_process("t1")
            self.assertEqual(len(mock_run.call_args_list), 1)
            self.assertEqual(mock_run.call_args_list[0].args[0][2], "agent-b")
