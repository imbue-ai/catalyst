from .base import Workflow
from .develop_theory import DevelopTheoryWorkflow
from .refine_theory_idea import RefineTheoryIdeaWorkflow

WORKFLOWS = {
    "develop-theory": DevelopTheoryWorkflow(),
    "refine-theory-idea": RefineTheoryIdeaWorkflow(),
}

def get_workflow(name: str) -> Workflow:
    return WORKFLOWS.get(name)
