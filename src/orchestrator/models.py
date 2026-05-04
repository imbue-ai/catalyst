from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELED = "canceled"

class Step(BaseModel):
    stage: str
    status: StepStatus = StepStatus.PENDING
    inputs: Dict[str, Any] = {}
    outputs: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    last_status: Optional[str] = None
    error: Optional[str] = None

class Addon(BaseModel):
    type: str # "streamline-theory", "review-theory", "refine-theory", "refinement-loop", "evolve-loop"
    theory_id: str
    direction: Optional[str] = None
    max_refinements: Optional[int] = None
    apply_expansions: Optional[str] = None
    evolve_iterations: Optional[int] = None
    num_parents: Optional[int] = None
    max_streamline_prob: Optional[float] = None
    num_extra_scores: Optional[int] = None
    review_id: Optional[str] = None
    hypothesis_title: Optional[str] = None
    instruction: Optional[str] = None

class Task(BaseModel):
    id: str
    title: Optional[str] = None
    workflow_inputs: Dict[str, Any] = {}
    env_folder: str
    framework: str # "gemini" or "claude"
    model: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    current_stage: Optional[str] = None
    steps: List[Step] = []
    addons: List[Addon] = []
    workflow_name: str = "develop-theory"
    workflow_structure: List[Dict[str, Any]] = []
    base_workflow_canceled: bool = False
    created_at: Optional[str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class TasksState(BaseModel):
    tasks: List[Task] = []
