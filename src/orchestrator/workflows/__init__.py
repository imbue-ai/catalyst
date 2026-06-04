from .base import Workflow
from .develop_theory import DevelopTheoryWorkflow
from .develop_theory_linear import DevelopTheoryLinearWorkflow
from .refine_theory_idea import RefineTheoryIdeaWorkflow
from .refine_theory_idea_linear import RefineTheoryIdeaLinearWorkflow
from .import_theory import ImportTheoryWorkflow
from .smoke import SmokeWorkflow

WORKFLOWS = {
    "develop-theory": DevelopTheoryWorkflow(),
    "develop-theory-linear": DevelopTheoryLinearWorkflow(),
    "refine-theory-idea": RefineTheoryIdeaWorkflow(),
    "refine-theory-idea-linear": RefineTheoryIdeaLinearWorkflow(),
    "import-theory": ImportTheoryWorkflow(),
    "smoke": SmokeWorkflow(),
}

def get_workflow(name: str) -> Workflow:
    return WORKFLOWS.get(name)
