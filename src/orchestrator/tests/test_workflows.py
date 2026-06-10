import unittest
from unittest.mock import patch, MagicMock, mock_open
from ..models import Task
from ..workflows.import_theory import ImportTheoryWorkflow
from ..workflows.develop_theory_linear import DevelopTheoryLinearWorkflow

class TestImportTheoryWorkflow(unittest.TestCase):
    def test_get_structure(self):
        task = Task(
            id="task_import_test",
            workflow_name="import-theory",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={"file_path": "/path/to/theory.txt"}
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
            workflow_inputs={"file_path": "/path/to/theory.txt"}
        )
        wf = ImportTheoryWorkflow()
        wf.init_db = MagicMock()
        mock_run_if_needed.return_value = {"theory_id": "T_imported"}
        mock_run_step = MagicMock()

        wf.run(task, mock_run_step)

        mock_run_summarize.assert_called_once_with(task, mock_run_step, "theory file at: /path/to/theory.txt")
        mock_run_if_needed.assert_called_once()
        self.assertEqual(mock_run_if_needed.call_args[0][2], "import-theory")


class TestDevelopTheoryLinearWorkflow(unittest.TestCase):
    def test_get_structure(self):
        task = Task(
            id="task_develop_linear_test",
            workflow_name="develop-theory-linear",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={"max_refinements": 2}
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
    @patch("orchestrator.workflows.develop_theory_linear.run_literature_review_and_exploration_parallel")
    @patch("orchestrator.workflows.develop_theory_linear.run_step_if_needed")
    @patch("orchestrator.workflows.develop_theory_linear.run_refinement_loop")
    @patch("builtins.open", new_callable=mock_open)
    def test_run_success(self, mock_file, mock_refinement_loop, mock_run_if_needed, mock_parallel, mock_summarize):
        task = Task(
            id="task_develop_linear_test",
            workflow_name="develop-theory-linear",
            framework="gemini",
            env_folder="/tmp/env",
            workflow_inputs={"phenomenon": "gravity", "max_refinements": 3}
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
        mock_summarize.assert_called_once_with(task, mock_run_step, "phenomenon: gravity")
        mock_parallel.assert_called_once_with(task, mock_run_step, "gravity")
        mock_run_if_needed.assert_called_once()
        mock_refinement_loop.assert_called_once_with(
            task,
            mock_run_step,
            "T1",
            "L1",
            apply_expansions=None,
            max_refinements=3,
            generate_intermediate_research_summaries=False
        )
