import json
import os
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
            env_folder=os.path.join(self.catalyst_dir, "e1"),
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
            env_folder=os.path.join(self.catalyst_dir, "e1"),
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
            env_folder=os.path.join(self.catalyst_dir, "e1"),
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
            env_folder=os.path.join(self.catalyst_dir, "e1"),
            workflow_inputs={}
        )
        add_task(task)
        self.assertEqual(len(get_tasks()), 1)

        delete_task("t1")
        self.assertEqual(len(get_tasks()), 0)

    def test_cancel_task_process_invokes_callbacks(self):
        """state.cancel_task_process must invoke every registered
        Cancellable's cancel callback with the configured timeout, then
        drop the entries from the registry."""
        from ..state import (
            Cancellable,
            cancel_task_process,
            register_cancellable,
            _running,
        )

        called_a, called_b = [], []
        a = Cancellable("a", lambda t: called_a.append(t))
        b = Cancellable("b", lambda t: called_b.append(t))
        register_cancellable("t1", a)
        register_cancellable("t1", b)

        cancel_task_process("t1", timeout=7)

        self.assertEqual(called_a, [7])
        self.assertEqual(called_b, [7])
        self.assertNotIn("t1", _running)

    def test_cancel_task_process_no_entries(self):
        from ..state import cancel_task_process
        # Cancelling a task with nothing registered must be a no-op.
        cancel_task_process("never-registered")

    def test_unregister_cancellable(self):
        from ..state import (
            Cancellable,
            cancel_task_process,
            register_cancellable,
            unregister_cancellable,
        )

        called_a, called_b = [], []
        a = Cancellable("a", lambda t: called_a.append(t))
        b = Cancellable("b", lambda t: called_b.append(t))
        register_cancellable("t1", a)
        register_cancellable("t1", b)
        unregister_cancellable("t1", a)

        cancel_task_process("t1")

        self.assertEqual(called_a, [])
        self.assertEqual(len(called_b), 1)

    def test_cancel_task_process_isolates_callback_errors(self):
        """A raising callback must not block subsequent callbacks; the
        registry should still be cleared on exit."""
        from ..state import (
            Cancellable,
            cancel_task_process,
            register_cancellable,
            _running,
        )

        called = []
        boom = Cancellable("boom", lambda t: (_ for _ in ()).throw(RuntimeError("boom")))
        good = Cancellable("good", lambda t: called.append(t))
        register_cancellable("t1", boom)
        register_cancellable("t1", good)

        cancel_task_process("t1", timeout=5)

        self.assertEqual(called, [5])
        self.assertNotIn("t1", _running)

    @patch("os.killpg")
    @patch("os.getpgid")
    def test_make_subprocess_cancellable_terminates_group(self, mock_getpgid, mock_killpg):
        """The cli_base helper wires SIGTERM-on-the-process-group into a
        Cancellable. End-to-end via the registry: registering the
        wrapper + cancelling the task must signal the group."""
        from ..agents.cli_base import make_subprocess_cancellable
        from ..state import cancel_task_process, register_cancellable

        mock_process = MagicMock()
        mock_process.pid = 123
        mock_getpgid.return_value = 456
        cancellable = make_subprocess_cancellable(mock_process, label="claude")
        register_cancellable("t1", cancellable)

        cancel_task_process("t1", timeout=5)

        mock_killpg.assert_called_with(456, 15)  # signal.SIGTERM is 15
        mock_process.wait.assert_called()

    def test_env_folder_relative_path_persistence(self):
        # 1. Create a task with an absolute env_folder under catalyst_dir
        task_id = "t_rel"
        abs_env_folder = os.path.join(self.catalyst_dir, "tasks", "task_t_rel")
        task = Task(
            id=task_id,
            workflow_name="w_rel",
            framework="f_rel",
            env_folder=abs_env_folder,
            workflow_inputs={}
        )
        add_task(task)

        # 2. In memory, it must remain absolute!
        retrieved = get_task(task_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.env_folder, abs_env_folder)

        # 3. On disk (in tasks_state.json), it must be persisted relative to CATALYST_PATH (which is catalyst_dir)
        with open(self.state_path, "r") as f:
            disk_data = json.load(f)
            disk_task = next(t for t in disk_data["tasks"] if t["id"] == task_id)
            # It should be relative: "tasks/task_t_rel"
            self.assertEqual(disk_task["env_folder"], "tasks/task_t_rel")

        # 4. Clear the in-memory cache to force a reload from disk, and load it again
        import orchestrator.state
        orchestrator.state._state_cache = None
        orchestrator.state._last_written_json = None

        reloaded = get_task(task_id)
        self.assertIsNotNone(reloaded)
        # It must be resolved back to the absolute path!
        self.assertEqual(reloaded.env_folder, abs_env_folder)

    def test_env_folder_outside_catalyst_path_remains_absolute(self):
        # 1. Create a task with an absolute env_folder OUTSIDE catalyst_dir
        task_id = "t_out"
        outside_folder = "/home/daniel/some_other_folder/task_t_out"
        task = Task(
            id=task_id,
            workflow_name="w_out",
            framework="f_out",
            env_folder=outside_folder,
            workflow_inputs={}
        )
        add_task(task)

        # 2. On disk, it must remain absolute!
        with open(self.state_path, "r") as f:
            disk_data = json.load(f)
            disk_task = next(t for t in disk_data["tasks"] if t["id"] == task_id)
            self.assertEqual(disk_task["env_folder"], outside_folder)

        # 3. Reload it and check it is still absolute
        import orchestrator.state
        orchestrator.state._state_cache = None
        orchestrator.state._last_written_json = None

        reloaded = get_task(task_id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.env_folder, outside_folder)

