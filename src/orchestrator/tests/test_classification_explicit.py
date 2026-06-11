import unittest
from unittest.mock import patch, MagicMock

from ..models import Task, StepCategory
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
