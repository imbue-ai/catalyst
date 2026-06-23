import unittest
from unittest.mock import patch, MagicMock, mock_open
from ..models import Task, Step, StepStatus, StepCategory
from ..workflows.common.title import run_summarize_title
from ..workflows.common.refinement import run_refinement_loop, get_active_max_iterations
from ..workflows.common.exploration import (
    run_literature_review_and_exploration_parallel,
)
from ..workflows.common.evolve import build_evolve_loop_structure, run_evolve_loop
from ..workflows.common.solve_goal_loop import (
    build_solve_goal_loop_structure,
    run_solve_goal_loop,
)
from ..workflows.common.evolve_solution import (
    build_evolve_solution_loop_structure,
    run_evolve_solution_loop,
)
from ..workflows.common.theory_initialization import run_initialize_theories


class TestWorkflowTitle(unittest.TestCase):
    def test_run_summarize_title_not_needed(self):
        task = Task(
            id="task_title_test",
            workflow_name="develop-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={},
            title="Existing Title",
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
            workflow_inputs={},
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
            workflow_inputs={},
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
            workflow_inputs={},
        )
        mock_run_step = MagicMock()

        # Iteration 1 review returns review ids, refine returns theory_id and major_changes=True
        # Iteration 2 review returns review ids, refine returns theory_id and major_changes=False (terminates)
        mock_run_if_needed.side_effect = [
            {"review_ids": ["R1", "R2"]},  # Iter 1 Review
            {"theory_id": "T2", "major_changes": True},  # Iter 1 Refine
            {"review_ids": ["R3"]},  # Iter 2 Review
            {"theory_id": "T3", "major_changes": False},  # Iter 2 Refine
        ]

        final_tid = run_refinement_loop(
            task=task,
            run_step_fn=mock_run_step,
            theory_id="T1",
            lit_review_id=None,
            apply_expansions=None,
            max_refinements=3,
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
            workflow_inputs={},
        )
        mock_run_step = MagicMock()
        mock_run_if_needed.return_value = {
            "review_ids": []
        }  # No reviews -> exits early

        final_tid = run_refinement_loop(
            task=task,
            run_step_fn=mock_run_step,
            theory_id="T1",
            lit_review_id=None,
            apply_expansions=None,
            max_refinements=3,
        )

        self.assertEqual(final_tid, "T1")
        mock_run_if_needed.assert_called_once()

    @patch("orchestrator.workflows.common.refinement.run_step_if_needed")
    def test_run_refinement_loop_with_summaries(self, mock_run_if_needed):
        task = Task(
            id="task_refine_test",
            workflow_name="develop-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={},
        )
        mock_run_step = MagicMock()

        # Iteration 1:
        # 1. Review (returns review ids)
        # 2. Summarize Research (returns something)
        # 3. Refine (returns theory_id and major_changes=True)
        # Iteration 2:
        # 4. Review (returns no review ids -> terminates)
        mock_run_if_needed.side_effect = [
            {"review_ids": ["R1", "R2"]},  # Iter 1 Review
            {"summary": "Summary of research"},  # Iter 1 Summarize Research
            {"theory_id": "T2", "major_changes": True},  # Iter 1 Refine
            {"review_ids": []},  # Iter 2 Review -> terminates
        ]

        final_tid = run_refinement_loop(
            task=task,
            run_step_fn=mock_run_step,
            theory_id="T1",
            lit_review_id=None,
            apply_expansions=None,
            max_refinements=3,
            generate_intermediate_research_summaries=True,
        )

        self.assertEqual(final_tid, "T2")
        self.assertEqual(mock_run_if_needed.call_count, 4)

        # Verify the specific stages in order
        calls = mock_run_if_needed.call_args_list
        self.assertEqual(calls[0][0][2], "review-theory-1")
        self.assertEqual(calls[1][0][2], "summarize-research-1")
        self.assertEqual(calls[2][0][2], "refine-theory-1")
        self.assertEqual(calls[3][0][2], "review-theory-2")


class TestWorkflowExploration(unittest.TestCase):
    @patch("orchestrator.workflows.common.exploration.get_step_output")
    def test_run_exploration_already_completed(self, mock_get_output):
        task = Task(
            id="task_explore_test",
            workflow_name="develop-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={},
        )
        mock_get_output.side_effect = [
            {"literature_review_id": "L123"},
            {"exploration_id": "E456"},
        ]
        mock_run_step = MagicMock()

        lit_id, exp_id = run_literature_review_and_exploration_parallel(
            task, mock_run_step, "phenomenon"
        )

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
            workflow_inputs={},
        )
        # Outputs do not exist
        mock_get_output.side_effect = [None, None]

        mock_run_step = MagicMock()
        mock_run_step.side_effect = [
            {"literature_review_id": "L999"},
            {"exploration_id": "E999"},
        ]

        lit_id, exp_id = run_literature_review_and_exploration_parallel(
            task, mock_run_step, "phenomenon"
        )

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
            workflow_inputs={},
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
    def test_run_evolve_loop_flow(
        self, mock_run_if_needed, mock_run_local_if_needed, mock_run_context
    ):
        task = Task(
            id="task_evolve_test",
            workflow_name="develop-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={},
        )
        mock_run_step = MagicMock()

        # 1. Parents Sample Res
        mock_run_local_if_needed.side_effect = [
            {
                "parents": [{"id": "T1", "subscores": {"length": 0.1}}]
            },  # Loop Iteration 1 Parents
            {"scoring_ids": ["T2"]},  # Loop Iteration 1 Scoring Sample
        ]

        # 2. Mutate + Review + Score Steps Mocking
        mock_run_if_needed.side_effect = [
            {"theory_id": "Tnew"},  # Mutation step (refine)
            {},  # Review step
            {},  # Score step
        ]

        run_evolve_loop(
            task=task,
            run_step_fn=mock_run_step,
            iterations=1,
            num_parents=1,
            max_streamline_prob=0.5,
            write_different_prob=0.2,
            num_extra_scores=1,
        )

        self.assertEqual(mock_run_local_if_needed.call_count, 2)
        self.assertEqual(mock_run_if_needed.call_count, 3)


class TestWorkflowSolveGoalLoop(unittest.TestCase):
    def test_build_solve_goal_loop_structure(self):
        task = Task(
            id="task_solve_goal_loop_test",
            workflow_name="solve-verifiable-goal-multi-strand",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={},
        )
        struct = build_solve_goal_loop_structure(
            task=task,
            num_strands=3,
            max_iterations=2,
            integration_interval=2,
            stage_prefix="test-",
        )
        self.assertEqual(struct["type"], "loop")
        self.assertEqual(struct["iterations"], 2)
        self.assertEqual(len(struct["iteration_structures"]), 2)

        # Iteration 1 has no integration
        iter1 = struct["iteration_structures"]["1"]
        self.assertEqual(len(iter1), 4)
        self.assertEqual(
            iter1[0]["stages"],
            [
                "test-propose-experiment-1-1",
                "test-propose-experiment-1-2",
                "test-propose-experiment-1-3",
            ],
        )

        # Iteration 2 has integration (integration_interval = 2)
        iter2 = struct["iteration_structures"]["2"]
        self.assertEqual(len(iter2), 5)
        self.assertEqual(iter2[4]["name"], "Integrate Interpretations")
        self.assertEqual(
            iter2[4]["stages"],
            [
                "test-integrate-interpretations-2-1",
                "test-integrate-interpretations-2-2",
                "test-integrate-interpretations-2-3",
            ],
        )

    @patch("orchestrator.workflows.common.solve_goal_loop.run_step_if_needed")
    def test_run_solve_goal_loop_success(self, mock_run_if_needed):
        task = Task(
            id="task_solve_goal_loop_test",
            workflow_name="solve-verifiable-goal-multi-strand",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={},
        )
        mock_run_step = MagicMock()

        # Configure mock responses for run_step_if_needed
        # 1. Propose Experiment 1-1, 1-2
        # 2. Rank Proposals 1
        # 3. Execute Proposal 1-1, 1-2
        # 4. Interpret Result 1-1, 1-2
        mock_run_if_needed.side_effect = [
            {"proposal_id": "prop-1-1"},  # Propose 1-1
            {"proposal_id": "prop-1-2"},  # Propose 1-2
            {"rankings": ["prop-1-1", "prop-1-2"], "solution_candidates": []},  # Rank
            {"experiment_id": "exp-1-1"},  # Execute prop-1-1
            {"experiment_id": "exp-1-2"},  # Execute prop-1-2
            {"theory_id": "theory-new-1-1"},  # Interpret 1-1
            {"theory_id": "theory-new-1-2"},  # Interpret 1-2
        ]

        final_theory_ids = run_solve_goal_loop(
            task=task,
            run_step=mock_run_step,
            theory_ids=["theory-1", "theory-2"],
            max_iterations=1,
            num_executions_per_iteration=2,
            execution_cost=1,
            integration_interval=5,
            stage_prefix="addon-1-",
        )

        self.assertEqual(final_theory_ids, ["theory-new-1-1", "theory-new-1-2"])
        self.assertEqual(mock_run_if_needed.call_count, 7)

    @patch("orchestrator.workflows.common.solve_goal_loop.run_step_if_needed")
    def test_run_solve_goal_loop_with_integration(self, mock_run_if_needed):
        task = Task(
            id="task_solve_goal_loop_test",
            workflow_name="solve-verifiable-goal-multi-strand",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={},
        )
        mock_run_step = MagicMock()

        # Configure mock responses for 1 iteration with integration_interval = 1
        mock_run_if_needed.side_effect = [
            {"proposal_id": "prop-1-1"},  # Propose 1-1
            {"proposal_id": "prop-1-2"},  # Propose 1-2
            {"rankings": ["prop-1-1", "prop-1-2"], "solution_candidates": []},  # Rank
            {"experiment_id": "exp-1-1"},  # Execute prop-1-1
            {"experiment_id": "exp-1-2"},  # Execute prop-1-2
            {"theory_id": "theory-new-1-1"},  # Interpret 1-1
            {"theory_id": "theory-new-1-2"},  # Interpret 1-2
            {"theory_ids": ["theory-integrated-1-1"]},  # Integrate 1-1
            {"theory_ids": ["theory-integrated-1-2"]},  # Integrate 1-2
        ]

        final_theory_ids = run_solve_goal_loop(
            task=task,
            run_step=mock_run_step,
            theory_ids=["theory-1", "theory-2"],
            max_iterations=1,
            num_executions_per_iteration=2,
            execution_cost=1,
            integration_interval=1,
            stage_prefix="addon-1-",
        )

        self.assertEqual(
            final_theory_ids, ["theory-integrated-1-1", "theory-integrated-1-2"]
        )
        self.assertEqual(mock_run_if_needed.call_count, 9)


class TestEvolveSolutionLoop(unittest.TestCase):
    def test_build_evolve_solution_loop_structure(self):
        task = Task(
            id="task_evolve_solution_loop_struct_test",
            workflow_name="solve-verifiable-goal",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={
                "num_strands": "2",
                "num_proposals": "2",
                "num_interpretations": "2",
                "num_parents": "2",
                "rescore_interval": "2",
            },
        )
        struct = build_evolve_solution_loop_structure(
            task=task,
            num_strands=2,
            max_iterations=2,
            stage_prefix="test-",
        )
        self.assertEqual(struct["type"], "loop")
        self.assertEqual(struct["iterations"], 2)
        self.assertEqual(len(struct["iteration_structures"]), 2)

        # Iteration 1: Regular iteration (steps 1-4 only)
        iter1 = struct["iteration_structures"]["1"]
        self.assertEqual(len(iter1), 6)
        self.assertEqual(iter1[0]["stage"], "test-sample-proposals-1")
        self.assertEqual(iter1[1]["name"], "Propose Experiments")
        self.assertEqual(iter1[2]["stage"], "test-rank-proposals-1")
        self.assertEqual(iter1[3]["name"], "Execute Proposals")
        self.assertEqual(iter1[4]["stage"], "test-sample-interpretations-1")
        self.assertEqual(iter1[5]["name"], "Interpret Results")

        # Iteration 2: Mutation iteration (steps 5-9 only, with added interpretation steps)
        iter2 = struct["iteration_structures"]["2"]
        self.assertEqual(len(iter2), 9)
        self.assertEqual(iter2[0]["stage"], "test-sample-integrate-parents-2")
        self.assertEqual(iter2[1]["name"], "Integrate Interpretations")
        self.assertEqual(iter2[2]["name"], "Propose Solution Candidates")
        self.assertEqual(iter2[3]["name"], "Execute Solution Candidates")
        self.assertEqual(iter2[4]["stage"], "test-sample-interpretations-2")
        self.assertEqual(iter2[5]["name"], "Interpret Results")
        self.assertEqual(iter2[6]["stage"], "test-sample-scoring-2")
        self.assertEqual(iter2[7]["stage"], "test-score-theory-solutions-2")
        self.assertEqual(iter2[8]["stage"], "test-summarize-goal-progress-2")

    @patch("orchestrator.workflows.common.evolve_solution.run_context_manager")
    @patch("orchestrator.workflows.common.evolve_solution.run_local_step_if_needed")
    @patch("orchestrator.workflows.common.evolve_solution.run_step_if_needed")
    def test_run_evolve_solution_loop_success(
        self, mock_run_if_needed, mock_run_local, mock_context_manager
    ):
        task = Task(
            id="task_evolve_solution_loop_run_test",
            workflow_name="solve-verifiable-goal",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={
                "num_proposals": "2",
                "num_interpretations": "2",
                "num_parents": "1",
                "num_extra_scores": "1",
                "rescore_interval": "2",
                "branch_prob": "0.0",
            },
        )
        mock_run_step = MagicMock()

        # Mocks setup:
        # Mock local steps (sampling)
        mock_run_local.side_effect = [
            {"samples": [{"id": "theory-1"}, {"id": "theory-2"}]},  # sample-proposals-1
            {"samples": [{"id": "theory-3"}]},  # sample-interpretations-1
            {"samples": [{"id": "theory-1"}]},  # sample-integrate-parents-2
            {"samples": [{"id": "theory-3"}]},  # sample-interpretations-2
            {
                "samples": [{"id": "theory-4", "latest_solution": "sol-latest"}]
            },  # sample-scoring-2
        ]

        # Mock standard/parallel steps
        mock_run_if_needed.side_effect = [
            # Iteration 1 (Regular)
            {"proposal_id": "prop-1-1"},  # Propose 1-1
            {"proposal_id": "prop-1-2"},  # Propose 1-2
            {"rankings": ["prop-1-1", "prop-1-2"], "solution_candidates": []},  # Rank 1
            {"experiment_id": "exp-1-1"},  # Execute prop-1-1
            {"experiment_id": "exp-1-2"},  # Execute prop-1-2
            {"theory_id": "theory-new-1-1"},  # Interpret 1-1 (theory-1)
            {"theory_id": "theory-new-1-2"},  # Interpret 1-2 (theory-2)
            {"theory_id": "theory-new-1-3"},  # Interpret 1-3 (theory-3)
            # Iteration 2 (Mutation)
            {"theory_ids": ["theory-1-integrated"]},  # Integrate 2-1
            {"proposal_id": "solution-prop-2"},  # Propose Solution ALWAYS
            {"solution_id": "solution-real-2"},  # Execute Solution Proposal
            {"theory_id": "theory-new-2-1"},  # Interpret 2-1 (theory-1-integrated)
            {"theory_id": "theory-new-2-2"},  # Interpret 2-2 (theory-3)
            {"status": "scored"},  # Score Theory Solutions
            {"status": "summarized"},  # Summarize Goal Progress 2
        ]

        run_evolve_solution_loop(
            task=task,
            run_step=mock_run_step,
            theory_ids=["theory-1", "theory-2"],
            max_iterations=2,
            stage_prefix="test-",
        )

        self.assertEqual(mock_run_local.call_count, 5)
        self.assertEqual(mock_run_if_needed.call_count, 15)

    def test_build_evolve_solution_loop_structure_with_summaries(self):
        task = Task(
            id="task_evolve_solution_loop_struct_test_summaries",
            workflow_name="solve-verifiable-goal",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={
                "num_strands": "2",
                "num_proposals": "2",
                "num_interpretations": "2",
                "num_parents": "2",
                "rescore_interval": "1",
            },
        )
        struct = build_evolve_solution_loop_structure(
            task=task,
            num_strands=2,
            max_iterations=2,
            stage_prefix="test-",
            generate_intermediate_research_summaries=True,
        )
        self.assertEqual(struct["type"], "loop")
        self.assertEqual(struct["iterations"], 2)
        self.assertEqual(len(struct["iteration_structures"]), 2)

        # Both iteration 1 and 2 are mutation iterations since rescore_interval=1
        # And since generate_intermediate_research_summaries is True, both must have a summary step at the end!
        iter1 = struct["iteration_structures"]["1"]
        self.assertEqual(len(iter1), 9)
        self.assertEqual(iter1[8]["stage"], "test-summarize-goal-progress-1")

        iter2 = struct["iteration_structures"]["2"]
        self.assertEqual(len(iter2), 9)
        self.assertEqual(iter2[8]["stage"], "test-summarize-goal-progress-2")

    @patch("orchestrator.workflows.common.evolve_solution.run_context_manager")
    @patch("orchestrator.workflows.common.evolve_solution.run_local_step_if_needed")
    @patch("orchestrator.workflows.common.evolve_solution.run_step_if_needed")
    def test_run_evolve_solution_loop_success_with_summaries(
        self, mock_run_if_needed, mock_run_local, mock_context_manager
    ):
        task = Task(
            id="task_evolve_solution_loop_run_test_summaries",
            workflow_name="solve-verifiable-goal",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={
                "num_proposals": "2",
                "num_interpretations": "2",
                "num_parents": "1",
                "num_extra_scores": "1",
                "rescore_interval": "1",
                "branch_prob": "0.0",
            },
        )
        mock_run_step = MagicMock()

        # Mocks setup:
        # Mock local steps (sampling)
        mock_run_local.side_effect = [
            {"samples": [{"id": "theory-1"}]},  # sample-integrate-parents-1
            {"samples": [{"id": "theory-3"}]},  # sample-interpretations-1
            {"samples": [{"id": "theory-4", "latest_solution": "sol-latest"}]},  # sample-scoring-1
            {"samples": [{"id": "theory-1"}]},  # sample-integrate-parents-2
            {"samples": [{"id": "theory-3"}]},  # sample-interpretations-2
            {"samples": [{"id": "theory-4", "latest_solution": "sol-latest"}]},  # sample-scoring-2
        ]

        # Mock standard/parallel steps
        mock_run_if_needed.side_effect = [
            # Iteration 1 (Mutation since rescore_interval=1)
            {"theory_ids": ["theory-1-integrated"]},  # Integrate 1-1
            {"proposal_id": "solution-prop-1"},  # Propose Solution ALWAYS
            {"solution_id": "solution-real-1"},  # Execute Solution Proposal
            {"theory_id": "theory-new-1-1"},  # Interpret 1-1 (theory-1-integrated)
            {"theory_id": "theory-new-1-2"},  # Interpret 1-2 (theory-3)
            {"status": "scored"},  # Score Theory Solutions 1
            {"status": "summarized"},  # Summarize Goal Progress 1
            # Iteration 2 (Mutation since rescore_interval=1)
            {"theory_ids": ["theory-2-integrated"]},  # Integrate 2-1
            {"proposal_id": "solution-prop-2"},  # Propose Solution ALWAYS
            {"solution_id": "solution-real-2"},  # Execute Solution Proposal
            {"theory_id": "theory-new-2-1"},  # Interpret 2-1 (theory-2-integrated)
            {"theory_id": "theory-new-2-2"},  # Interpret 2-2 (theory-3)
            {"status": "scored"},  # Score Theory Solutions 2
            {"status": "summarized"},  # Summarize Goal Progress 2
        ]

        run_evolve_solution_loop(
            task=task,
            run_step=mock_run_step,
            theory_ids=["theory-1", "theory-2"],
            max_iterations=2,
            stage_prefix="test-",
            generate_intermediate_research_summaries=True,
        )

        self.assertEqual(mock_run_local.call_count, 6)
        self.assertEqual(mock_run_if_needed.call_count, 14)


class TestTheoryInitialization(unittest.TestCase):
    @patch(
        "orchestrator.workflows.common.theory_initialization.run_local_step_if_needed"
    )
    @patch("orchestrator.workflows.common.theory_initialization.run_context_manager")
    @patch("tempfile.mkdtemp")
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.makedirs")
    def test_run_initialize_theories_success(
        self,
        mock_makedirs,
        mock_file,
        mock_mkdtemp,
        mock_context_manager,
        mock_run_local,
    ):
        task = Task(
            id="task_test",
            workflow_name="solve-verifiable-goal",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={
                "goal": "Test Goal String",
                "num_strands": "2",
            },
        )
        mock_mkdtemp.side_effect = ["/tmp/env/tmp/dir1", "/tmp/env/tmp/dir2"]
        mock_context_manager.side_effect = [
            "Result stored with ID: T_1",
            "Result stored with ID: T_2",
        ]

        # Simulating run_local_step_if_needed calling the inner fn
        def run_local_side_effect(task, stage, fn):
            return fn()

        mock_run_local.side_effect = run_local_side_effect

        theory_ids = run_initialize_theories(task)

        self.assertEqual(theory_ids, ["T_1", "T_2"])
        mock_makedirs.assert_called_once_with("/tmp/env/tmp", exist_ok=True)
        self.assertEqual(mock_mkdtemp.call_count, 2)
        self.assertEqual(mock_context_manager.call_count, 2)
        mock_file.assert_any_call("/tmp/env/tmp/dir1/theory.md", "w", encoding="utf-8")
        mock_file.assert_any_call("/tmp/env/tmp/dir2/theory.md", "w", encoding="utf-8")

    @patch(
        "orchestrator.workflows.common.theory_initialization.run_local_step_if_needed"
    )
    def test_run_initialize_theories_canceled(self, mock_run_local):
        task = Task(
            id="task_test",
            workflow_name="solve-verifiable-goal",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={
                "goal": "Test Goal String",
                "num_strands": "2",
            },
        )
        mock_run_local.return_value = {"_canceled": True}
        theory_ids = run_initialize_theories(task)
        self.assertIsNone(theory_ids)
