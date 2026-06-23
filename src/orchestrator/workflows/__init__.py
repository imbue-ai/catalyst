from .base import Workflow
from .develop_theory import DevelopTheoryWorkflow
from .develop_theory_linear import DevelopTheoryLinearWorkflow
from .refine_theory_idea import RefineTheoryIdeaWorkflow
from .refine_theory_idea_linear import RefineTheoryIdeaLinearWorkflow
from .import_theory import ImportTheoryWorkflow
from .smoke import SmokeWorkflow
from .solve_verifiable_goal_multi_strand import SolveVerifiableGoalMultiStrandWorkflow
from .solve_verifiable_goal import SolveVerifiableGoalWorkflow

WORKFLOWS = {
    "develop-theory": DevelopTheoryWorkflow(),
    "develop-theory-linear": DevelopTheoryLinearWorkflow(),
    "refine-theory-idea": RefineTheoryIdeaWorkflow(),
    "refine-theory-idea-linear": RefineTheoryIdeaLinearWorkflow(),
    "import-theory": ImportTheoryWorkflow(),
    "smoke": SmokeWorkflow(),
    "solve-verifiable-goal-multi-strand": SolveVerifiableGoalMultiStrandWorkflow(),
    "solve-verifiable-goal": SolveVerifiableGoalWorkflow(),
}


def get_workflow(name: str) -> Workflow:
    return WORKFLOWS.get(name)
