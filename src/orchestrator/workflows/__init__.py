from .base import Workflow
from .develop_theory import DevelopTheoryWorkflow
from .refine_theory_idea import RefineTheoryIdeaWorkflow
from .import_theory import ImportTheoryWorkflow

WORKFLOWS = {
    "develop-theory": DevelopTheoryWorkflow(),
    "refine-theory-idea": RefineTheoryIdeaWorkflow(),
    "import-theory": ImportTheoryWorkflow(),
}

def get_workflow(name: str) -> Workflow:
    return WORKFLOWS.get(name)
