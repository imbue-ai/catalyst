from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

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

class Step(BaseModel):
    stage: str
    status: StepStatus = StepStatus.PENDING
    inputs: Dict[str, Any] = {}
    outputs: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    last_status: Optional[str] = None
    error: Optional[str] = None

class Addon(BaseModel):
    type: str # "streamline-theory", "review-theory", "refine-theory"
    theory_id: str
    direction: Optional[str] = None

class Task(BaseModel):
    id: str
    title: Optional[str] = None
    workflow_inputs: Dict[str, Any] = {}
    env_folder: str
    framework: str # "gemini" or "claude"
    model: Optional[str] = None
    db_path: str
    status: TaskStatus = TaskStatus.PENDING
    current_stage: Optional[str] = None
    steps: List[Step] = []
    addons: List[Addon] = []
    workflow_name: str = "develop-theory"
    workflow_structure: List[Dict[str, Any]] = []

class TasksState(BaseModel):
    tasks: List[Task] = []
