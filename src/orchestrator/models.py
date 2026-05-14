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
    WAITING = "waiting"
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
    # Identifier surfaced by the dashboard's "Inspect Agent" panel.
    # For legacy `claude` / `gemini` frameworks this is the claude /
    # gemini CLI session UUID (use `claude --resume <session_id>` /
    # `gemini --resume <session_id>` to attach). For `mngr-claude` /
    # `mngr-gemini` this is the mngr agent name
    # (e.g. "aisci-abcd1234-write-theory-7f3a"); use
    # `MNGR_HOST_DIR=~/.mngr-ai-scientist mngr connect <session_id>`.
    # The frontend picks the right command from `task.framework`.
    session_id: Optional[str] = None
    last_status: Optional[str] = None
    error: Optional[str] = None

class Addon(BaseModel):
    type: str # "streamline-theory", "review-theory", "refine-theory", "refinement-loop", "evolve-loop"
    theory_id: Optional[str] = None
    theory_ids: Optional[List[str]] = None
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
    lit_review_id: Optional[str] = None

class Task(BaseModel):
    id: str
    title: Optional[str] = None
    workflow_inputs: Dict[str, Any] = {}
    env_folder: str
    framework: str  # "claude", "gemini", "mngr-claude", or "mngr-gemini"
    model: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    current_stage: Optional[str] = None
    steps: List[Step] = []
    addons: List[Addon] = []
    workflow_name: str = "develop-theory"
    workflow_structure: List[Dict[str, Any]] = []
    created_at: Optional[str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class TasksState(BaseModel):
    tasks: List[Task] = []
