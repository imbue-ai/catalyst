import unittest
from unittest.mock import patch, MagicMock, mock_open
from ..models import Task
from ..workflows.import_theory import ImportTheoryWorkflow
from ..workflows.develop_theory_linear import DevelopTheoryLinearWorkflow
from ..workflows.solve_verifiable_goal_multi_strand import (
    SolveVerifiableGoalMultiStrandWorkflow,
)
from ..workflows.solve_verifiable_goal import SolveVerifiableGoalWorkflow


class TestImportTheoryWorkflow(unittest.TestCase):
    def test_get_structure(self):
        task = Task(
            id="task_import_test",
            workflow_name="import-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={"file_path": "/path/to/theory.txt"},
        )
        wf = ImportTheoryWorkflow()
        self.assertEqual(wf.name, "import-theory")
        struct = wf.get_structure(task)
        self.assertEqual(len(struct), 2)
        self.assertEqual(struct[0]["stage"], "summarize-title")
        self.assertEqual(struct[1]["stage"], "import-theory")

    @patch("orchestrator.workflows.import_theory.run_summarize_title")
    @patch("orchestrator.workflows.import_theory.run_step_if_needed")
    def test_run_success(self, mock_run_if_needed, mock_run_summarize):
        task = Task(
            id="task_import_test",
            workflow_name="import-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={"file_path": "/path/to/theory.txt"},
        )
        wf = ImportTheoryWorkflow()
        wf.init_db = MagicMock()
        mock_run_if_needed.return_value = {"theory_id": "T_imported"}
        mock_run_step = MagicMock()

        wf.run(task, mock_run_step)

        mock_run_summarize.assert_called_once_with(
            task, mock_run_step, "theory file at: /path/to/theory.txt"
        )
        mock_run_if_needed.assert_called_once()
        self.assertEqual(mock_run_if_needed.call_args[0][2], "import-theory")


class TestDevelopTheoryLinearWorkflow(unittest.TestCase):
    def test_get_structure(self):
        task = Task(
            id="task_develop_linear_test",
            workflow_name="develop-theory-linear",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={"max_refinements": 2},
        )
        wf = DevelopTheoryLinearWorkflow()
        self.assertEqual(wf.name, "develop-theory-linear")
        struct = wf.get_structure(task)
        self.assertEqual(struct[0]["stage"], "summarize-title")
        self.assertEqual(struct[1]["name"], "Gather Context")
        self.assertEqual(struct[2]["stage"], "write-theory")
        self.assertEqual(struct[3]["type"], "loop")
        self.assertEqual(struct[3]["iterations"], 2)

    @patch("orchestrator.workflows.develop_theory_linear.run_summarize_title")
    @patch(
        "orchestrator.workflows.develop_theory_linear.run_literature_review_and_exploration_parallel"
    )
    @patch("orchestrator.workflows.develop_theory_linear.run_step_if_needed")
    @patch("orchestrator.workflows.develop_theory_linear.run_refinement_loop")
    @patch("builtins.open", new_callable=mock_open)
    def test_run_success(
        self,
        mock_file,
        mock_refinement_loop,
        mock_run_if_needed,
        mock_parallel,
        mock_summarize,
    ):
        task = Task(
            id="task_develop_linear_test",
            workflow_name="develop-theory-linear",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={"phenomenon": "gravity", "max_refinements": 3},
        )
        wf = DevelopTheoryLinearWorkflow()
        wf.init_db = MagicMock()
        mock_parallel.return_value = ("L1", "E1")
        mock_run_if_needed.return_value = {"theory_id": "T1"}
        mock_run_step = MagicMock()

        wf.run(task, mock_run_step)

        # Assert writing phenomenon file
        mock_file.assert_called_once_with("/tmp/env/phenomenon.txt", "w")
        mock_file().write.assert_called_once_with("gravity\n")

        # Assert correct helper and step invocations
        mock_summarize.assert_called_once_with(
            task, mock_run_step, "phenomenon: gravity"
        )
        mock_parallel.assert_called_once_with(task, mock_run_step, "gravity")
        mock_run_if_needed.assert_called_once()
        mock_refinement_loop.assert_called_once_with(
            task,
            mock_run_step,
            "T1",
            "L1",
            apply_expansions=None,
            max_refinements=3,
            generate_intermediate_research_summaries=False,
        )


class TestSolveVerifiableGoalMultiStrandWorkflow(unittest.TestCase):
    def test_get_structure(self):
        task = Task(
            id="task_solve_verifiable_test",
            workflow_name="solve-verifiable-goal-multi-strand",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={
                "goal": "Test goal",
                "verification_instructions": "Verify nicely",
                "num_strands": "2",
                "max_iterations": "1",
            },
        )
        wf = SolveVerifiableGoalMultiStrandWorkflow()
        self.assertEqual(wf.name, "solve-verifiable-goal-multi-strand")
        struct = wf.get_structure(task)
        self.assertEqual(struct[0]["stage"], "summarize-title")
        self.assertEqual(struct[1]["stage"], "initialize-theories")
        self.assertEqual(len(struct), 3)

    @patch(
        "orchestrator.workflows.solve_verifiable_goal_multi_strand.run_summarize_title"
    )
    @patch(
        "orchestrator.workflows.solve_verifiable_goal_multi_strand.run_initialize_theories"
    )
    @patch("orchestrator.workflows.common.solve_goal_loop.run_step_if_needed")
    @patch("builtins.open", new_callable=mock_open)
    def test_run_success(
        self, mock_file, mock_run_if_needed, mock_run_local, mock_summarize
    ):
        task = Task(
            id="task_solve_verifiable_test",
            workflow_name="solve-verifiable-goal-multi-strand",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={
                "goal": "Test goal",
                "verification_instructions": "Verify nicely",
                "num_strands": "2",
                "max_iterations": "1",
            },
        )
        wf = SolveVerifiableGoalMultiStrandWorkflow()
        mock_run_step = MagicMock()

        # Step 1: Initialize Theories returns theory IDs
        mock_run_local.return_value = ["T_1", "T_2"]

        # Configure mock_run_if_needed to return expected keys/dicts for different stages
        def run_step_side_effect(
            task, run_step, stage_name, prompt, category, **kwargs
        ):
            if "propose-experiment" in stage_name:
                return {"proposal_id": "O_prop"}
            elif "rank-proposals" in stage_name:
                return {"rankings": ["O_prop"], "solution_candidates": []}
            elif "execute-proposal" in stage_name:
                return {"experiment_id": "X_exp"}
            elif "interpret-result" in stage_name:
                return {"theory_id": "T_new"}
            return {}

        mock_run_if_needed.side_effect = run_step_side_effect

        wf.run(task, mock_run_step)

        # Assert correct files written
        mock_file.assert_any_call("/tmp/env/goal.txt", "w")
        mock_file.assert_any_call("/tmp/env/verification_instructions.txt", "w")

        # Check summarize and step invocations
        mock_summarize.assert_called_once_with(task, mock_run_step, "goal: Test goal")
        mock_run_local.assert_called_once()

    @patch(
        "orchestrator.workflows.solve_verifiable_goal_multi_strand.run_summarize_title"
    )
    @patch(
        "orchestrator.workflows.solve_verifiable_goal_multi_strand.run_initialize_theories"
    )
    @patch("orchestrator.workflows.common.solve_goal_loop.run_step_if_needed")
    @patch("builtins.open", new_callable=mock_open)
    def test_run_rankings_empty(
        self, mock_file, mock_run_if_needed, mock_run_local, mock_summarize
    ):
        task = Task(
            id="task_solve_verifiable_test",
            workflow_name="solve-verifiable-goal-multi-strand",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={
                "goal": "Test goal",
                "verification_instructions": "Verify nicely",
                "num_strands": "2",
                "max_iterations": "1",
            },
        )
        wf = SolveVerifiableGoalMultiStrandWorkflow()
        mock_run_step = MagicMock()

        # Step 1: Initialize Theories returns theory IDs
        mock_run_local.return_value = ["T_1", "T_2"]

        # Configure mock_run_if_needed: Propose returns O_prop, Rank returns empty lists
        def run_step_side_effect(
            task, run_step, stage_name, prompt, category, **kwargs
        ):
            if "propose-experiment" in stage_name:
                return {"proposal_id": "O_prop"}
            elif "rank-proposals" in stage_name:
                return {"rankings": [], "solution_candidates": []}
            return {}

        mock_run_if_needed.side_effect = run_step_side_effect

        # This should complete early without exception
        wf.run(task, mock_run_step)

        # Ensure we didn't call execute-proposal
        for call_args in mock_run_if_needed.call_args_list:
            self.assertNotIn("execute-proposal", call_args[0][2])

    @patch(
        "orchestrator.workflows.solve_verifiable_goal_multi_strand.run_summarize_title"
    )
    @patch(
        "orchestrator.workflows.solve_verifiable_goal_multi_strand.run_initialize_theories"
    )
    @patch("orchestrator.workflows.common.solve_goal_loop.run_step_if_needed")
    @patch("builtins.open", new_callable=mock_open)
    def test_run_missing_key_failure(
        self, mock_file, mock_run_if_needed, mock_run_local, mock_summarize
    ):
        task = Task(
            id="task_solve_verifiable_test",
            workflow_name="solve-verifiable-goal-multi-strand",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={
                "goal": "Test goal",
                "verification_instructions": "Verify nicely",
                "num_strands": "2",
                "max_iterations": "1",
            },
        )
        wf = SolveVerifiableGoalMultiStrandWorkflow()
        mock_run_step = MagicMock()

        mock_run_local.return_value = ["T_1", "T_2"]

        # Propose fails to return expected key proposal_id (returns invalid_key instead)
        mock_run_if_needed.return_value = {"invalid_key": "some_value"}

        # This should raise an exception
        with self.assertRaises(Exception) as context:
            wf.run(task, mock_run_step)

        self.assertIn("Failed to generate all 2 proposals", str(context.exception))

    def test_get_structure_with_integration(self):
        task = Task(
            id="task_solve_verifiable_test_integration",
            workflow_name="solve-verifiable-goal-multi-strand",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={
                "goal": "Test goal",
                "verification_instructions": "Verify nicely",
                "num_strands": "2",
                "max_iterations": "2",
                "integration_interval": "2",
            },
        )
        wf = SolveVerifiableGoalMultiStrandWorkflow()
        struct = wf.get_structure(task)
        self.assertEqual(len(struct), 3)
        loop_struct = struct[2]
        self.assertEqual(loop_struct["type"], "loop")
        iter_structures = loop_struct["iteration_structures"]
        # Iteration 1 (i = 1): 1 % 2 != 0 -> 4 stages (no Integrate)
        self.assertEqual(len(iter_structures["1"]), 4)
        # Iteration 2 (i = 2): 2 % 2 == 0 -> 5 stages (with Integrate)
        self.assertEqual(len(iter_structures["2"]), 5)
        self.assertEqual(iter_structures["2"][4]["name"], "Integrate Interpretations")

    @patch(
        "orchestrator.workflows.solve_verifiable_goal_multi_strand.run_summarize_title"
    )
    @patch(
        "orchestrator.workflows.solve_verifiable_goal_multi_strand.run_initialize_theories"
    )
    @patch("orchestrator.workflows.common.solve_goal_loop.run_step_if_needed")
    @patch("builtins.open", new_callable=mock_open)
    def test_run_success_with_integration(
        self, mock_file, mock_run_if_needed, mock_run_local, mock_summarize
    ):
        task = Task(
            id="task_solve_verifiable_test_with_integration",
            workflow_name="solve-verifiable-goal-multi-strand",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={
                "goal": "Test goal",
                "verification_instructions": "Verify nicely",
                "num_strands": "2",
                "max_iterations": "1",
                "integration_interval": "1",
            },
        )
        wf = SolveVerifiableGoalMultiStrandWorkflow()
        mock_run_step = MagicMock()

        # Step 1: Initialize Theories returns theory IDs
        mock_run_local.return_value = ["T_1", "T_2"]

        # Configure mock_run_if_needed to return expected keys/dicts for different stages
        def run_step_side_effect(
            task, run_step, stage_name, prompt, category, **kwargs
        ):
            if "propose-experiment" in stage_name:
                return {"proposal_id": "O_prop"}
            elif "rank-proposals" in stage_name:
                return {"rankings": ["O_prop"], "solution_candidates": []}
            elif "execute-proposal" in stage_name:
                return {"experiment_id": "X_exp"}
            elif "interpret-result" in stage_name:
                return {"theory_id": "T_new"}
            elif "integrate-interpretations" in stage_name:
                return {"theory_ids": ["T_integrated"]}
            return {}

        mock_run_if_needed.side_effect = run_step_side_effect

        wf.run(task, mock_run_step)

        # Check summarize and step invocations
        mock_summarize.assert_called_once_with(task, mock_run_step, "goal: Test goal")
        mock_run_local.assert_called_once()

        # Verify that integrate-interpretations was indeed called
        any_integrate_calls = any(
            "integrate-interpretations" in call.args[2]
            for call in mock_run_if_needed.call_args_list
        )
        self.assertTrue(any_integrate_calls)


class TestSolveVerifiableGoalWorkflow(unittest.TestCase):
    def test_get_structure(self):
        task = Task(
            id="task_solve_verifiable_test",
            workflow_name="solve-verifiable-goal",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={
                "goal": "Test goal",
                "verification_instructions": "Verify nicely",
                "num_strands": "2",
                "max_iterations": "1",
            },
        )
        wf = SolveVerifiableGoalWorkflow()
        self.assertEqual(wf.name, "solve-verifiable-goal")
        struct = wf.get_structure(task)
        self.assertEqual(struct[0]["stage"], "summarize-title")
        self.assertEqual(struct[1]["stage"], "initialize-theories")
        self.assertEqual(struct[2]["stage"], "initialize-solutions")
        self.assertEqual(len(struct), 4)

    @patch("orchestrator.workflows.solve_verifiable_goal.run_summarize_title")
    @patch("orchestrator.workflows.solve_verifiable_goal.run_initialize_theories")
    @patch("orchestrator.workflows.solve_verifiable_goal.run_initialize_solutions")
    @patch("orchestrator.workflows.common.evolve_solution.run_local_step_if_needed")
    @patch("builtins.open", new_callable=mock_open)
    def test_run_success(
        self, mock_file, mock_run_evolve_step, mock_run_init_solutions, mock_run_local, mock_summarize
    ):
        task = Task(
            id="task_solve_verifiable_test",
            workflow_name="solve-verifiable-goal",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={
                "goal": "Test goal",
                "verification_instructions": "Verify nicely",
                "num_strands": "2",
                "max_iterations": "1",
            },
        )
        wf = SolveVerifiableGoalWorkflow()
        mock_run_step = MagicMock()

        # Step 1: Initialize Theories returns theory IDs
        mock_run_local.return_value = ["T_1", "T_2"]
        mock_run_init_solutions.return_value = [("S_1", "T_1"), ("S_2", "T_2")]

        wf.run(task, mock_run_step)

        # Assert correct files written
        mock_file.assert_any_call("/tmp/env/goal.txt", "w")
        mock_file.assert_any_call("/tmp/env/verification_instructions.txt", "w")

        # Check summarize and step invocations
        mock_summarize.assert_called_once_with(task, mock_run_step, "goal: Test goal")
        mock_run_local.assert_called_once()
        mock_run_init_solutions.assert_called_once()
        mock_run_evolve_step.assert_called_once()

