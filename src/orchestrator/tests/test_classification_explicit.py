import unittest
from unittest.mock import patch, MagicMock

from ..models import Task, StepCategory, AgentSettings, Step, StepStatus
from ..orchestrator import _run_step_core
from ..addons import get_addon_handler
from ..workflows.import_theory import ImportTheoryWorkflow
from ..workflows.smoke import SmokeWorkflow
from ..workflows.develop_theory_linear import DevelopTheoryLinearWorkflow

class TestExplicitClassification(unittest.TestCase):
    def test_all_addons_categories(self):
        # We check the category property of each registered addon
        addons_and_expected_categories = {
            "streamline-theory": StepCategory.THEORY_WRITING,
            "review-theory": StepCategory.REVIEW,
            "refine-theory": StepCategory.THEORY_WRITING,
            "refinement-loop": StepCategory.MISC,
            "evolve-loop": StepCategory.MISC,
            "polish-theory": StepCategory.THEORY_WRITING,
            "refine-hypothesis": StepCategory.THEORY_WRITING,
            "falsify-hypothesis": StepCategory.REVIEW,
            "suggest-expansions": StepCategory.REVIEW,
            "expand-theory": StepCategory.THEORY_WRITING,
            "review-adherence": StepCategory.REVIEW,
            "improve-adherence": StepCategory.THEORY_WRITING,
            "streamline-theory-variations": StepCategory.THEORY_WRITING,
            "edit-theory": StepCategory.THEORY_WRITING,
            "score-theories": StepCategory.REVIEW,
            "write-different-theory": StepCategory.THEORY_WRITING,
            "summarize-research": StepCategory.MISC,
            "solve-goal-loop": StepCategory.MISC,
            "evolve-solution-loop": StepCategory.MISC,
        }

        for name, expected_cat in addons_and_expected_categories.items():
            handler = get_addon_handler(name)
            self.assertIsNotNone(handler, f"Addon {name} should exist.")
            self.assertEqual(
                handler.category,
                expected_cat,
                f"Addon {name} category should be {expected_cat}, got {handler.category}"
            )

    @patch("orchestrator.workflows.import_theory.run_summarize_title")
    @patch("orchestrator.workflows.import_theory.run_step_if_needed")
    def test_import_theory_workflow_category(self, mock_run_if_needed, mock_summarize):
        task = Task(
            id="test_task_import",
            workflow_name="import-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={"file_path": "/path/to/theory.txt"}
        )
        wf = ImportTheoryWorkflow()
        wf.init_db = MagicMock()
        mock_run_if_needed.return_value = {"theory_id": "T_imported"}
        mock_run_step = MagicMock()

        wf.run(task, mock_run_step)

        mock_run_if_needed.assert_called_once_with(
            task,
            mock_run_step,
            "import-theory",
            unittest.mock.ANY,
            StepCategory.THEORY_WRITING,
        )

    @patch("orchestrator.workflows.smoke.run_step_if_needed")
    def test_smoke_workflow_category(self, mock_run_if_needed):
        task = Task(
            id="test_task_smoke",
            workflow_name="smoke",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={}
        )
        wf = SmokeWorkflow()
        mock_run_step = MagicMock()

        wf.run(task, mock_run_step)

        mock_run_if_needed.assert_called_once_with(
            task,
            mock_run_step,
            "smoke",
            unittest.mock.ANY,
            StepCategory.MISC,
        )

    @patch("orchestrator.workflows.develop_theory_linear.run_summarize_title")
    @patch("orchestrator.workflows.develop_theory_linear.run_literature_review_and_exploration_parallel")
    @patch("orchestrator.workflows.develop_theory_linear.run_step_if_needed")
    @patch("orchestrator.workflows.develop_theory_linear.run_refinement_loop")
    @patch("builtins.open")
    def test_develop_theory_linear_workflow_category(
        self, mock_file, mock_refinement_loop, mock_run_if_needed, mock_parallel, mock_summarize
    ):
        task = Task(
            id="test_task_develop_linear",
            workflow_name="develop-theory-linear",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={"phenomenon": "gravity", "max_refinements": 0}
        )
        wf = DevelopTheoryLinearWorkflow()
        wf.init_db = MagicMock()
        mock_parallel.return_value = ("L1", "E1")
        mock_run_if_needed.return_value = {"theory_id": "T1"}
        mock_run_step = MagicMock()

        wf.run(task, mock_run_step)

        # The first run_step_if_needed is "write-theory" (THEORY_WRITING)
        mock_run_if_needed.assert_any_call(
            task,
            mock_run_step,
            "write-theory",
            unittest.mock.ANY,
            StepCategory.THEORY_WRITING,
        )

    @patch("orchestrator.orchestrator.get_agent_runner")
    @patch("orchestrator.orchestrator.get_task_lock")
    @patch("orchestrator.orchestrator.update_task")
    @patch("orchestrator.orchestrator.get_task")
    @patch("orchestrator.orchestrator.run_context_manager")
    def test_per_category_routing_resolution(self, mock_run_context_manager, mock_get_task, mock_update_task, mock_get_task_lock, mock_get_agent_runner):


        # Set up runner mock
        mock_runner = MagicMock()
        mock_get_agent_runner.return_value = mock_runner
        mock_runner.build_common_environment_variables.return_value = {}
        mock_runner.run.return_value = ("output", "session_123", None)

        # Set up a task with defaults and overrides
        task = Task(
            id="test_task_routing",
            framework="gemini",
            model="gemini-1.5-pro",
            effort="medium",
            env_folder="/tmp/env",
            steps=[Step(stage="test-stage", status=StepStatus.RUNNING)],
            category_overrides={
                StepCategory.THEORY_WRITING: AgentSettings(
                    framework="claude",
                    model="claude-3-opus",
                    effort="high",
                ),
                StepCategory.REVIEW: AgentSettings(
                    model="claude-3-sonnet", # overrides model only, framework and effort fall back
                )
            }
        )

        mock_get_task.return_value = task

        # Case 1: Active override for StepCategory.THEORY_WRITING (complete override)
        _run_step_core(task, stage="test-stage", prompt="Write something", category=StepCategory.THEORY_WRITING)
        mock_get_agent_runner.assert_called_with("claude")
        mock_runner.run.assert_called_with(
            task_id=task.id,
            prompt="Write something",
            env_folder=task.env_folder,
            stage="test-stage",
            common_environment_variables={},
            model="claude-3-opus",
            effort="high",
            on_session_id=unittest.mock.ANY,
            on_status=unittest.mock.ANY,
        )

        # Case 2: Partial override for StepCategory.REVIEW (only model is overridden, framework & effort fall back)
        mock_get_agent_runner.reset_mock()
        mock_runner.run.reset_mock()
        _run_step_core(task, stage="test-stage", prompt="Review this", category=StepCategory.REVIEW)
        mock_get_agent_runner.assert_called_with("gemini") # falls back to task framework
        mock_runner.run.assert_called_with(
            task_id=task.id,
            prompt="Review this",
            env_folder=task.env_folder,
            stage="test-stage",
            common_environment_variables={},
            model="claude-3-sonnet", # overridden
            effort="medium", # falls back to task effort
            on_session_id=unittest.mock.ANY,
            on_status=unittest.mock.ANY,
        )

        # Case 3: No override for StepCategory.MISC (everything falls back)
        mock_get_agent_runner.reset_mock()
        mock_runner.run.reset_mock()
        _run_step_core(task, stage="test-stage", prompt="Misc work", category=StepCategory.MISC)
        mock_get_agent_runner.assert_called_with("gemini") # falls back
        mock_runner.run.assert_called_with(
            task_id=task.id,
            prompt="Misc work",
            env_folder=task.env_folder,
            stage="test-stage",
            common_environment_variables={},
            model="gemini-1.5-pro", # falls back
            effort="medium", # falls back
            on_session_id=unittest.mock.ANY,
            on_status=unittest.mock.ANY,
        )
