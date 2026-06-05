import unittest
import json
import logging
from unittest.mock import patch, MagicMock, mock_open
from fastapi.testclient import TestClient
from fastapi import Response

from server import app
from orchestrator.models import Task, TaskStatus, Step, StepStatus

# Silence logs during tests
logging.disable(logging.CRITICAL)

client = TestClient(app)

class TestServerEndpoints(unittest.TestCase):
    def setUp(self):
        self.dummy_task = Task(
            id="test_task_123",
            workflow_inputs={"phenomenon": "test phenomenon"},
            framework="test_framework",
            env_folder="/fake/env/folder",
            status=TaskStatus.RUNNING,
            steps=[],
            addons=[],
            workflow_name="develop-theory",
            workflow_structure=[]
        )
        self.path_patcher = patch("server.get_catalyst_path", return_value="/tmp/test_catalyst")
        self.path_patcher.start()

    def tearDown(self):
        self.path_patcher.stop()

    @patch("server.get_tasks")
    def test_get_tasks(self, mock_get_tasks):
        mock_get_tasks.return_value = [self.dummy_task]
        response = client.get("/api/tasks")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        task_json = response.json()[0]
        self.assertEqual(task_json["id"], "test_task_123")
        self.assertNotIn("steps", task_json)
        self.assertNotIn("addons", task_json)
        self.assertNotIn("workflow_structure", task_json)
        self.assertNotIn("guidance", task_json)
        self.assertNotIn("workflow_inputs", task_json)

    @patch("server.get_task")
    def test_get_task(self, mock_get_task):
        mock_get_task.return_value = self.dummy_task
        response = client.get("/api/tasks/test_task_123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "test_task_123")

    @patch("server.os.path.isdir")
    @patch("server.os.listdir")
    def test_get_templates(self, mock_listdir, mock_isdir):
        mock_isdir.return_value = True
        mock_listdir.return_value = ["template1", "template2"]
        response = client.get("/api/templates")
        self.assertEqual(response.status_code, 200)
        self.assertIn("template1", response.json())

    @patch("server.subprocess.run")
    @patch("server.add_task")
    @patch("server.start_task")
    def test_create_task(self, mock_start_task, mock_add_task, mock_run):
        task_req = {
            "workflow_name": "develop-theory",
            "workflow_inputs": {"phenomenon": "new"},
            "framework": "claude"
        }
        response = client.post("/api/tasks", data={"request": json.dumps(task_req)})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_add_task.called)
        self.assertTrue(mock_start_task.called)

    @patch("server.subprocess.run")
    @patch("server.add_task")
    @patch("server.start_task")
    @patch("server.shutil.copyfileobj")
    @patch("server.zipfile.ZipFile")
    @patch("server.os.makedirs")
    @patch("server.os.remove")
    @patch("builtins.open", new_callable=mock_open)
    def test_create_task_with_file(self, mock_file, mock_remove, mock_makedirs, mock_zip, mock_copy, mock_start_task, mock_add_task, mock_run):
        task_req = {
            "workflow_name": "import-theory",
            "workflow_inputs": {},
            "framework": "claude"
        }
        file_content = b"fake zip content"
        file = ("test.zip", file_content, "application/zip")
        
        response = client.post(
            "/api/tasks",
            data={"request": json.dumps(task_req)},
            files={"file": file}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_zip.called)
        self.assertEqual(response.json()["workflow_inputs"]["file_path"], "tmp/import (a zip archive was unpacked into this folder)")

    @patch("server.get_task")
    @patch("server.update_task")
    def test_add_task_addon(self, mock_update_task, mock_get_task):
        mock_get_task.return_value = self.dummy_task
        addon_req = {"type": "streamline-theory", "theory_id": "T_123"}
        response = client.post("/api/tasks/test_task_123/addons", json=addon_req)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["addons"]), 1)
        self.assertTrue(mock_update_task.called)

    @patch("server.get_task")
    def test_cancel_step(self, mock_get_task):
        task_with_step = self.dummy_task.model_copy(deep=True)
        task_with_step.steps = [Step(stage="test_stage", status=StepStatus.PENDING)]
        mock_get_task.return_value = task_with_step
        response = client.post("/api/tasks/test_task_123/steps/test_stage/cancel")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "canceled")

    @patch("server.get_task")
    def test_bulk_cancel_steps(self, mock_get_task):
        task_with_steps = self.dummy_task.model_copy(deep=True)
        task_with_steps.steps = [Step(stage="s1", status=StepStatus.RUNNING), Step(stage="s2", status=StepStatus.RUNNING)]
        mock_get_task.return_value = task_with_steps
        response = client.post("/api/tasks/test_task_123/steps/bulk-cancel", json={"stages": ["s1", "s2"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "canceled")

    @patch("server.get_task")
    @patch("server.update_task")
    @patch("server.cancel_task_process")
    def test_cancel_task(self, mock_cancel_task_process, mock_update_task, mock_get_task):
        mock_get_task.return_value = self.dummy_task
        response = client.post("/api/tasks/test_task_123/cancel")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_cancel_task_process.called)

    @patch("server.get_task")
    @patch("server.start_task")
    def test_resume_task(self, mock_start_task, mock_get_task):
        paused_task = self.dummy_task.model_copy(deep=True)
        paused_task.status = TaskStatus.PAUSED
        mock_get_task.return_value = paused_task
        response = client.post("/api/tasks/test_task_123/resume")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_start_task.called)

    @patch("server.get_task")
    @patch("server.update_task")
    @patch("builtins.open", new_callable=mock_open)
    def test_update_task_guidance(self, mock_file, mock_update_task, mock_get_task):
        mock_get_task.return_value = self.dummy_task
        guidance_req = {"guidance": "New custom user guidance."}
        response = client.post("/api/tasks/test_task_123/guidance", json=guidance_req)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["guidance"], "New custom user guidance.")
        self.assertTrue(mock_update_task.called)
        mock_file.assert_called_once_with("/fake/env/folder/GUIDANCE.txt", "w", encoding="utf-8")

    @patch("server.get_task")
    @patch("server.cancel_task_process")
    @patch("server.os.path.exists")
    @patch("server.shutil.rmtree")
    @patch("server.delete_task")
    def test_delete_task(self, mock_delete_task, mock_rmtree, mock_exists, mock_cancel, mock_get_task):
        mock_get_task.return_value = self.dummy_task
        mock_exists.return_value = True
        with patch("server.os.path.isdir", return_value=True):
            response = client.delete("/api/tasks/test_task_123")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_delete_task.called)

    @patch("server.get_task")
    @patch("server.subprocess.run")
    def test_get_task_theories(self, mock_run, mock_get_task):
        mock_get_task.return_value = self.dummy_task
        mock_res = MagicMock()
        mock_res.stdout = '[{"id": "T_1", "score": 1.0}]'
        mock_run.return_value = mock_res
        response = client.get("/api/tasks/test_task_123/theories")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], "T_1")

    def test_get_harnesses(self):
        response = client.get("/api/harnesses")
        self.assertEqual(response.status_code, 200)
        harnesses = response.json()
        self.assertEqual(len(harnesses), 5)
        claude = next(h for h in harnesses if h["name"] == "claude")
        self.assertEqual(claude["display_name"], "Claude Code (claude -p)")
        self.assertIn("opus", claude["models"])
        mngr_claude = next(h for h in harnesses if h["name"] == "mngr-claude")
        self.assertEqual(mngr_claude["display_name"], "Claude Code (mngr)")

    @patch("server.get_task")
    @patch("server.os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="content")
    def test_get_artifact_primary(self, mock_file, mock_exists, mock_get_task):
        mock_get_task.return_value = self.dummy_task
        mock_exists.return_value = True

        response = client.get("/api/tasks/test_task_123/artifacts/T_123/primary")
        self.assertEqual(response.status_code, 200)
        from server import inject_disclaimer
        self.assertEqual(response.json()["content"], inject_disclaimer("content"))

    @patch("server.get_task")
    @patch("server.os.path.exists")
    @patch("server.FileResponse")
    def test_get_artifact_file(self, mock_FileResponse, mock_exists, mock_get_task):
        mock_get_task.return_value = self.dummy_task
        mock_exists.return_value = True
        mock_FileResponse.return_value = Response(content="filecontent")
        response = client.get("/api/tasks/test_task_123/artifacts/T_123/files/file.txt")
        self.assertEqual(response.status_code, 200)

    @patch("server.get_task")
    @patch("server.os.path.exists")
    def test_export_artifact_multiline_regex(self, mock_exists, mock_get_task):
        """
        Verify export endpoint successfully packages multiline markdown images.
        """
        mock_get_task.return_value = self.dummy_task
        mock_exists.return_value = True

        md_content = '''Here is some text.
![Multi-line
alt text
example](image.png)
More text.'''

        with patch("builtins.open", mock_open(read_data=md_content)):
            with patch("server.os.path.isfile", return_value=True):
                with patch("server.os.path.abspath", side_effect=lambda x: x): # prevent traversal check failure
                    with patch("zipfile.ZipFile.write") as mock_zip_write:
                        with patch("zipfile.ZipFile.writestr") as mock_zip_writestr:
                            response = client.get("/api/tasks/test_task_123/artifacts/T_123/export")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/zip")

        # Verify that zipfile.writestr was called with theory.md
        writestr_args = [call_args[0][0] for call_args in mock_zip_writestr.call_args_list]
        self.assertIn("T_123/theory.md", writestr_args)

        # Verify that zipfile.write was called with image.png
        write_args = [call_args[0][1] for call_args in mock_zip_write.call_args_list]
        self.assertIn("T_123/image.png", write_args)

    @patch("server.get_catalyst_path", return_value="/tmp/test_catalyst")
    @patch("server.open")
    @patch("server.fcntl.flock")
    @patch("server.initialize_state")
    @patch("server.shutdown_all")
    @patch("server.os.makedirs")
    def test_lifespan_lock_success(self, mock_makedirs, mock_shutdown_all, mock_initialize_state, mock_flock, mock_open_file, mock_get_path):
        import asyncio
        from server import lifespan

        # Mock the opened lock file
        mock_file = MagicMock()
        mock_file.fileno.return_value = 123
        mock_open_file.return_value = mock_file

        async def run_lifespan():
            async with lifespan(None):
                pass

        asyncio.run(run_lifespan())

        # Check that we made the directory and opened the lock file
        mock_makedirs.assert_called_with("/tmp/test_catalyst", exist_ok=True)
        mock_open_file.assert_called_with("/tmp/test_catalyst/server.lock", "w")

        # Check that we acquired and released the lock
        import fcntl
        mock_flock.assert_any_call(123, fcntl.LOCK_EX | fcntl.LOCK_NB)
        mock_flock.assert_any_call(123, fcntl.LOCK_UN)
        mock_file.close.assert_called()

    @patch("server.get_catalyst_path", return_value="/tmp/test_catalyst")
    @patch("server.open")
    @patch("server.fcntl.flock")
    @patch("server.os.makedirs")
    def test_lifespan_lock_already_locked(self, mock_makedirs, mock_flock, mock_open_file, mock_get_path):
        import asyncio
        from server import lifespan

        # Mock lock failure
        mock_file = MagicMock()
        mock_file.fileno.return_value = 123
        mock_open_file.return_value = mock_file
        mock_flock.side_effect = BlockingIOError("Lock already held")

        async def run_lifespan():
            async with lifespan(None):
                pass

        with self.assertRaises(RuntimeError) as ctx:
            asyncio.run(run_lifespan())

        self.assertEqual(str(ctx.exception), "Another server instance is already running.")
        mock_file.close.assert_called_once()

if __name__ == '__main__':
    unittest.main()