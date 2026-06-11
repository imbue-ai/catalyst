import unittest
from unittest.mock import patch, MagicMock
from ..models import Task, Step, StepStatus, StepCategory
from ..workflows.common.title import run_summarize_title
from ..workflows.common.refinement import run_refinement_loop, get_active_max_iterations
from ..workflows.common.exploration import run_literature_review_and_exploration_parallel
from ..workflows.common.evolve import build_evolve_loop_structure, run_evolve_loop

class TestWorkflowTitle(unittest.TestCase):
    def test_run_summarize_title_not_needed(self):
        task = Task(
            id="task_title_test",
            workflow_name="develop-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={},
            title="Existing Title"
        )
        mock_run_step = MagicMock()
        run_summarize_title(task, mock_run_step, "description")
        mock_run_step.assert_not_called()

    @patch("orchestrator.workflows.common.title.run_step_if_needed")
    def test_run_summarize_title_needed(self, mock_run_if_needed):
        task = Task(
            id="task_title_test",
            workflow_name="develop-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={}
        )
        mock_run_if_needed.return_value = {"title": "Generated Title"}
        mock_run_step = MagicMock()
        
        run_summarize_title(task, mock_run_step, "description")
        
        self.assertEqual(task.title, "Generated Title")
        mock_run_if_needed.assert_called_once_with(
            task,
            mock_run_step,
            "summarize-title",
            unittest.mock.ANY,
            StepCategory.MISC,
        )


class TestWorkflowRefinement(unittest.TestCase):
    def test_get_active_max_iterations(self):
        task = Task(
            id="task_refine_test",
            workflow_name="develop-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={}
        )
        # Default with no steps
        self.assertEqual(get_active_max_iterations(task, 3), 3)

        # Step matching review-theory-X
        task.steps.append(Step(stage="review-theory-2", status=StepStatus.COMPLETED))
        self.assertEqual(get_active_max_iterations(task, 1), 2)

        # Step matching refine-theory-Y
        task.steps.append(Step(stage="refine-theory-5", status=StepStatus.COMPLETED))
        self.assertEqual(get_active_max_iterations(task, 3), 5)

        # Unmatching step
        task.steps.append(Step(stage="other-step-9", status=StepStatus.COMPLETED))
        self.assertEqual(get_active_max_iterations(task, 3), 5)

    @patch("orchestrator.workflows.common.refinement.run_step_if_needed")
    def test_run_refinement_loop_success(self, mock_run_if_needed):
        task = Task(
            id="task_refine_test",
            workflow_name="develop-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={}
        )
        mock_run_step = MagicMock()
        
        # Iteration 1 review returns review ids, refine returns theory_id and major_changes=True
        # Iteration 2 review returns review ids, refine returns theory_id and major_changes=False (terminates)
        mock_run_if_needed.side_effect = [
            {"review_ids": ["R1", "R2"]}, # Iter 1 Review
            {"theory_id": "T2", "major_changes": True}, # Iter 1 Refine
            {"review_ids": ["R3"]}, # Iter 2 Review
            {"theory_id": "T3", "major_changes": False} # Iter 2 Refine
        ]

        final_tid = run_refinement_loop(
            task=task,
            run_step_fn=mock_run_step,
            theory_id="T1",
            lit_review_id=None,
            apply_expansions=None,
            max_refinements=3
        )

        self.assertEqual(final_tid, "T3")
        self.assertEqual(mock_run_if_needed.call_count, 4)

    @patch("orchestrator.workflows.common.refinement.run_step_if_needed")
    def test_run_refinement_loop_no_reviews(self, mock_run_if_needed):
        task = Task(
            id="task_refine_test",
            workflow_name="develop-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={}
        )
        mock_run_step = MagicMock()
        mock_run_if_needed.return_value = {"review_ids": []} # No reviews -> exits early

        final_tid = run_refinement_loop(
            task=task,
            run_step_fn=mock_run_step,
            theory_id="T1",
            lit_review_id=None,
            apply_expansions=None,
            max_refinements=3
        )

        self.assertEqual(final_tid, "T1")
        mock_run_if_needed.assert_called_once()


class TestWorkflowExploration(unittest.TestCase):
    @patch("orchestrator.workflows.common.exploration.get_step_output")
    def test_run_exploration_already_completed(self, mock_get_output):
        task = Task(
            id="task_explore_test",
            workflow_name="develop-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={}
        )
        mock_get_output.side_effect = [
            {"literature_review_id": "L123"},
            {"exploration_id": "E456"}
        ]
        mock_run_step = MagicMock()

        lit_id, exp_id = run_literature_review_and_exploration_parallel(task, mock_run_step, "phenomenon")
        
        self.assertEqual(lit_id, "L123")
        self.assertEqual(exp_id, "E456")
        mock_run_step.assert_not_called()

    @patch("orchestrator.workflows.common.exploration.get_step_output")
    def test_run_exploration_needed(self, mock_get_output):
        task = Task(
            id="task_explore_test",
            workflow_name="develop-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={}
        )
        # Outputs do not exist
        mock_get_output.side_effect = [None, None]
        
        mock_run_step = MagicMock()
        mock_run_step.side_effect = [
            {"literature_review_id": "L999"},
            {"exploration_id": "E999"}
        ]

        lit_id, exp_id = run_literature_review_and_exploration_parallel(task, mock_run_step, "phenomenon")
        
        self.assertEqual(lit_id, "L999")
        self.assertEqual(exp_id, "E999")
        self.assertEqual(mock_run_step.call_count, 2)


class TestWorkflowEvolve(unittest.TestCase):
    def test_build_evolve_loop_structure(self):
        task = Task(
            id="task_evolve_test",
            workflow_name="develop-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={}
        )
        structs = build_evolve_loop_structure(task, 2)
        self.assertEqual(len(structs), 1)
        self.assertEqual(structs[0]["type"], "loop")
        self.assertEqual(structs[0]["iterations"], 2)
        self.assertIn("1", structs[0]["iteration_structures"])
        self.assertIn("2", structs[0]["iteration_structures"])

    @patch("orchestrator.workflows.common.evolve.run_context_manager")
    @patch("orchestrator.workflows.common.evolve.run_local_step_if_needed")
    @patch("orchestrator.workflows.common.evolve.run_step_if_needed")
    def test_run_evolve_loop_flow(self, mock_run_if_needed, mock_run_local_if_needed, mock_run_context):
        task = Task(
            id="task_evolve_test",
            workflow_name="develop-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={}
        )
        mock_run_step = MagicMock()

        # 1. Parents Sample Res
        mock_run_local_if_needed.side_effect = [
            {"parents": [{"id": "T1", "subscores": {"length": 0.1}}]}, # Loop Iteration 1 Parents
            {"scoring_ids": ["T2"]} # Loop Iteration 1 Scoring Sample
        ]

        # 2. Mutate + Review + Score Steps Mocking
        mock_run_if_needed.side_effect = [
            {"theory_id": "Tnew"}, # Mutation step (refine)
            {}, # Review step
            {} # Score step
        ]

        run_evolve_loop(
            task=task,
            run_step_fn=mock_run_step,
            iterations=1,
            num_parents=1,
            max_streamline_prob=0.5,
            write_different_prob=0.2,
            num_extra_scores=1
        )

        self.assertEqual(mock_run_local_if_needed.call_count, 2)
        self.assertEqual(mock_run_if_needed.call_count, 3)
