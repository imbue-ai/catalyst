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


class StepCategory(str, Enum):
    THEORY_WRITING = "THEORY_WRITING"
    REVIEW = "REVIEW"
    MISC = "MISC"



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
    # For the direct `claude` / `gemini` frameworks this is the CLI session
    # UUID (use `claude --resume <session_id>` / `gemini --resume
    # <session_id>` to attach); the direct `agy` framework has no resumable
    # session id. For `mngr-claude` / `mngr-antigravity` this is the mngr
    # agent name (e.g. "cata-abcd1234-write-theory-7f3a"); use
    # `MNGR_HOST_DIR=~/.mngr-catalyst uv run mngr connect <session_id>`.
    # The frontend picks the right command from `task.framework`.
    session_id: Optional[str] = None
    last_status: Optional[str] = None
    error: Optional[str] = None


class Addon(BaseModel):
    type: str  # "streamline-theory", "review-theory", "refine-theory", "refinement-loop", "evolve-loop", "write-different-theory"
    theory_id: Optional[str] = None
    theory_ids: Optional[List[str]] = None
    direction: Optional[str] = None
    max_refinements: Optional[int] = None
    apply_expansions: Optional[str] = None
    evolve_iterations: Optional[int] = None
    num_parents: Optional[int] = None
    max_streamline_prob: Optional[float] = None
    write_different_prob: Optional[float] = None
    num_extra_scores: Optional[int] = None
    review_id: Optional[str] = None
    hypothesis_title: Optional[str] = None
    instruction: Optional[str] = None
    lit_review_id: Optional[str] = None
    generate_intermediate_research_summaries: Optional[bool] = None


class TheoryScoringWeights(BaseModel):
    correctness_weight: float = Field(..., ge=0.0, le=1.0)
    power_weight: float = Field(..., ge=0.0, le=1.0)
    adherence_weight: float = Field(..., ge=0.0, le=1.0)


class AgentSettings(BaseModel):
    framework: Optional[str] = None
    model: Optional[str] = None
    effort: Optional[str] = None


class Task(BaseModel):
    id: str
    title: Optional[str] = None
    workflow_inputs: Dict[str, Any] = {}
    env_folder: str
    framework: str  # "gemini", "claude", "agy", "mngr-claude", or "mngr-antigravity"
    model: Optional[str] = None
    effort: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    current_stage: Optional[str] = None
    steps: List[Step] = []
    addons: List[Addon] = []
    workflow_name: str = "develop-theory"
    workflow_structure: List[Dict[str, Any]] = []
    guidance: str = ""
    theory_scoring_weights: Optional[TheoryScoringWeights] = None
    created_at: Optional[str] = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    generate_summary: bool = False
    category_overrides: Dict[StepCategory, AgentSettings] = Field(default_factory=dict)


class TaskShallow(BaseModel):
    id: str
    title: Optional[str] = None
    env_folder: str
    framework: str
    model: Optional[str] = None
    effort: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    current_stage: Optional[str] = None
    workflow_name: str = "develop-theory"
    created_at: Optional[str] = None
    category_overrides: Dict[StepCategory, AgentSettings] = Field(default_factory=dict)


class TasksState(BaseModel):
    tasks: List[Task] = []
