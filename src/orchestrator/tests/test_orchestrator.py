from unittest.mock import patch, MagicMock
from .helpers import OrchestratorTestCase
from ..orchestrator import _run_step_core, _orchestrate_task
from ..models import Task, StepStatus, TaskStatus, Step, StepCategory
from ..state import add_task

class TestOrchestrator(OrchestratorTestCase):
    def setUp(self):
        super().setUp()
        self.task = Task(
            id="task_1",
            workflow_name="develop-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={}
        )
        # We need to add the task to the state so get_task works
        add_task(self.task)

    @patch("orchestrator.orchestrator.get_agent_runner")
    @patch("orchestrator.orchestrator.run_context_manager")
    @patch("orchestrator.orchestrator.update_task")
    @patch("orchestrator.orchestrator.get_task")
    def test_run_step_success(self, mock_get_task, mock_update_task, mock_run_ctx, mock_get_runner):
        mock_runner = MagicMock()
        mock_runner.run.return_value = ({"theory_id": "T1"}, "sid123", None)
        mock_get_runner.return_value = mock_runner
        mock_get_task.return_value = self.task
        
        # _run_step_core expects the step to already exist in the task
        self.task.steps.append(Step(stage="stage1", status=StepStatus.RUNNING))
        
        result = _run_step_core(self.task, "stage1", "prompt1", StepCategory.MISC)
        
        self.assertEqual(result, {"theory_id": "T1"})
        self.assertEqual(self.task.steps[0].status, StepStatus.COMPLETED)
        
        # Verify commit was called
        mock_run_ctx.assert_called()
        commit_args = mock_run_ctx.call_args[0][1]
        self.assertEqual(commit_args[0], "commit")
        self.assertTrue(commit_args[1].startswith("tx_"))

    @patch("orchestrator.orchestrator.get_agent_runner")
    @patch("orchestrator.orchestrator.run_context_manager")
    def test_run_step_failure(self, mock_run_ctx, mock_get_runner):
        mock_runner = MagicMock()
        mock_runner.run.return_value = (None, "sid123", "Agent error")
        mock_get_runner.return_value = mock_runner
        
        # _run_step_core expects the step to already exist
        self.task.steps.append(Step(stage="stage1", status=StepStatus.RUNNING))
        
        with self.assertRaises(Exception) as cm:
            _run_step_core(self.task, "stage1", "prompt1", StepCategory.MISC)
        
        self.assertIn("Agent error", str(cm.exception))
        self.assertEqual(self.task.steps[0].status, StepStatus.FAILED)
        mock_run_ctx.assert_not_called()

    @patch("orchestrator.orchestrator.get_workflow")
    @patch("orchestrator.orchestrator.get_task")
    @patch("orchestrator.orchestrator.update_task")
    def test_orchestrate_task_flow(self, mock_update, mock_get_task, mock_get_workflow):
        mock_get_task.return_value = self.task
        
        mock_workflow = MagicMock()
        mock_get_workflow.return_value = mock_workflow
        
        # We need to mock get_addon_handler too if task.addons is empty it's fine
        self.task.addons = []
        
        _orchestrate_task(self.task.id)
        
        self.assertEqual(self.task.status, TaskStatus.COMPLETED)
        mock_workflow.run.assert_called_once()

    @patch("orchestrator.orchestrator.get_workflow")
    @patch("orchestrator.orchestrator.get_task")
    @patch("orchestrator.orchestrator.update_task")
    def test_orchestrate_task_already_running(self, mock_update, mock_get_task, mock_get_workflow):
        running_task = self.task.model_copy(deep=True)
        running_task.status = TaskStatus.RUNNING
        mock_get_task.return_value = running_task
        
        mock_workflow = MagicMock()
        mock_get_workflow.return_value = mock_workflow
        
        _orchestrate_task(self.task.id)
        
        # It should return early and not get/run the workflow
        mock_get_workflow.assert_not_called()

