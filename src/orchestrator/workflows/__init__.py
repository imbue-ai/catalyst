from .base import Workflow
from .develop_theory import DevelopTheoryWorkflow

WORKFLOWS = {
    "develop-theory": DevelopTheoryWorkflow(),
}

def get_workflow(name: str) -> Workflow:
    return WORKFLOWS.get(name)
