import uuid
import os
import shutil
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from orchestrator.models import Task, TaskStatus
from orchestrator.state import get_tasks, get_task, add_task, update_task, cancel_task_process, delete_task, initialize_state, shutdown_all
from orchestrator.orchestrator import start_task
from context_manager import PREFIX_TO_CATEGORY, CATEGORY_MD_MAP

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)-9s %(message)s")
logger = logging.getLogger(__name__)

class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.args and len(record.args) >= 5:
            method, status = record.args[1], record.args[4]
            if method == "GET" and status == 200:
                return False
        return True

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Apply filter to uvicorn access logger
    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())
    
    # Initialize state on startup (move RUNNING to PAUSED)
    initialize_state()
    yield
    # Clean up processes on shutdown
    logger.info("[SERVER] Shutting down, cleaning up processes...")
    shutdown_all()

app = FastAPI(title="AI Scientist Orchestrator", lifespan=lifespan)

# Enable CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class CreateTaskRequest(BaseModel):
    workflow_name: str
    workflow_inputs: Dict[str, Any]
    template_folder: Optional[str] = None
    framework: str
    model: Optional[str] = None

@app.get("/api/tasks", response_model=List[Task])
def list_tasks():
    return get_tasks()

@app.get("/api/tasks/{task_id}", response_model=Task)
def get_task_details(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/api/tasks", response_model=Task)
def create_task(req: CreateTaskRequest):
    task_id = str(uuid.uuid4())

    # Generate unique target path inside ./research
    target_path = os.path.abspath(os.path.join(".", "research", f"task_{task_id[:8]}"))

    # Run create_environment.py
    cmd = ["python", "create_environment.py", target_path]
    if req.template_folder:
        abs_template = os.path.abspath(req.template_folder)
        if not os.path.exists(abs_template) or not os.path.isdir(abs_template):
            raise HTTPException(status_code=400, detail=f"Template folder does not exist: {req.template_folder}")
        cmd.extend(["--template", abs_template])

    try:
        import subprocess
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to create environment: {e}")

    # Inject summary into workflow_inputs
    inputs = dict(req.workflow_inputs)
    summary_candidate = inputs.get("phenomenon") or inputs.get("idea") or ""
    inputs["summary"] = summary_candidate

    task = Task(
        id=task_id,
        workflow_inputs=inputs,
        env_folder=target_path,
        framework=req.framework,
        model=req.model,
        status=TaskStatus.PENDING,
        steps=[],
        workflow_name=req.workflow_name
    )

    add_task(task)
    start_task(task)
    return task
class CreateAddonRequest(BaseModel):
    type: str
    theory_id: str
    direction: Optional[str] = None

@app.post("/api/tasks/{task_id}/addons", response_model=Task)
def create_addon(task_id: str, req: CreateAddonRequest):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    from orchestrator.models import Addon, StepStatus, Step
    
    if task.status not in (TaskStatus.COMPLETED, TaskStatus.RUNNING):
        # Cancel all remaining steps if adding addon to an incomplete workflow
        task.base_workflow_canceled = True
        
        # Mark pending/running/paused/failed base steps and existing addon steps as CANCELED
        from orchestrator.workflows import get_workflow
        from orchestrator.orchestrator import get_full_structure
        workflow = get_workflow(task.workflow_name)
        if workflow:
            # Get the full structure BEFORE adding the new addon
            base_struct = get_full_structure(workflow, task)
            
            # Helper to extract all stages
            all_stages = []
            for item in base_struct:
                if item["type"] == "step":
                    all_stages.append(item["stage"])
                elif item["type"] == "parallel":
                    all_stages.extend(item.get("stages", []))
                elif item["type"] == "loop":
                    iterations = item.get("iterations", 3)
                    for i in range(1, iterations + 1):
                        for b_stage in item.get("base_stages", []):
                            all_stages.append(f"{b_stage}-{i}")
            
            # Now ensure they are in task.steps as CANCELED if not COMPLETED
            existing_stages = {s.stage: s for s in task.steps}
            for stage in all_stages:
                if stage in existing_stages:
                    if existing_stages[stage].status not in (StepStatus.COMPLETED, StepStatus.CANCELED):
                        existing_stages[stage].status = StepStatus.CANCELED
                else:
                    task.steps.append(Step(stage=stage, status=StepStatus.CANCELED))
                    
            # Set the task itself to completed so the orchestrator loop won't hang if we start it just for the addon
            # wait, if we set it to completed, start_task won't run it? 
            # Actually, start_task doesn't check for COMPLETED, it just checks for RUNNING.
            # However, if it's FAILED or PAUSED, it resumes.
    
    addon = Addon(type=req.type, theory_id=req.theory_id, direction=req.direction)
    task.addons.append(addon)
    
    from orchestrator.orchestrator import get_full_structure
    from orchestrator.workflows import get_workflow
    workflow = get_workflow(task.workflow_name)
    task.workflow_structure = get_full_structure(workflow, task)
    
    update_task(task)
    
    if task.status != TaskStatus.RUNNING:
        start_task(task)
        
    return task

@app.post("/api/tasks/{task_id}/steps/{stage}/cancel")
def cancel_step(task_id: str, stage: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    from orchestrator.models import StepStatus
    
    # If the step is currently running, we might need to cancel the process
    # but the simplest way is to just cancel the task and restart it, or just let it fail.
    # Actually, we can just mark it as canceled if it's paused, failed, or pending.
    step = next((s for s in task.steps if s.stage == stage), None)
    if step:
        if step.status in (StepStatus.FAILED, StepStatus.PAUSED, StepStatus.PENDING):
            step.status = StepStatus.CANCELED
            update_task(task)
            return {"status": "canceled"}
        else:
            raise HTTPException(status_code=400, detail="Can only cancel steps in failed, paused, or pending state")
    else:
        # Step not in task.steps yet (so it's pending in the structure)
        from orchestrator.models import Step
        task.steps.append(Step(stage=stage, status=StepStatus.CANCELED))
        update_task(task)
        return {"status": "canceled"}

class BulkCancelRequest(BaseModel):
    stages: List[str]

@app.post("/api/tasks/{task_id}/steps/bulk-cancel")
def bulk_cancel_steps(task_id: str, req: BulkCancelRequest):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    from orchestrator.models import StepStatus, Step
    
    modified = False
    existing_stages = {s.stage: s for s in task.steps}
    
    for stage in set(req.stages):
        step = existing_stages.get(stage)
        if step:
            if step.status in (StepStatus.FAILED, StepStatus.PAUSED, StepStatus.PENDING):
                step.status = StepStatus.CANCELED
                modified = True
        else:
            task.steps.append(Step(stage=stage, status=StepStatus.CANCELED))
            modified = True
            
    if modified:
        update_task(task)
        
    return {"status": "canceled"}

@app.post("/api/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.status = TaskStatus.PAUSED
    update_task(task)
    cancel_task_process(task_id)
    return {"status": "paused"}

@app.post("/api/tasks/{task_id}/resume")
def resume_task(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status == TaskStatus.RUNNING:
        return task
        
    start_task(task)
    return task

@app.delete("/api/tasks/{task_id}")
def remove_task(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 1. Cancel process if running
    cancel_task_process(task_id)
    
    # 2. Delete database folder
    if os.path.exists(task.env_folder):
        try:
            if os.path.isdir(task.env_folder):
                shutil.rmtree(task.env_folder)
            else:
                os.remove(task.env_folder)
        except Exception as e:
            logger.error(f"Error deleting env_folder {task.env_folder}: {e}")

    # 3. Remove from state
    delete_task(task_id)
    return {"status": "deleted"}

@app.get("/api/tasks/{task_id}/artifacts/{artifact_id}/primary")
def get_artifact_primary(task_id: str, artifact_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    prefix = artifact_id.split('_')[0]
    category = PREFIX_TO_CATEGORY.get(prefix)
    if not category:
        raise HTTPException(status_code=400, detail="Invalid artifact ID prefix")
        
    md_filename = CATEGORY_MD_MAP.get(category)
    if not md_filename:
        raise HTTPException(status_code=500, detail="No primary markdown configured for category")
        
    file_path = os.path.join(task.env_folder, ".ai-scientist-db", category, artifact_id, md_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Artifact file not found")
        
    with open(file_path, "r", encoding="utf-8") as f:
        return {"content": f.read()}

@app.get("/api/tasks/{task_id}/artifacts/{artifact_id}/files/{file_path:path}")
def get_artifact_file(task_id: str, artifact_id: str, file_path: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    prefix = artifact_id.split('_')[0]
    category = PREFIX_TO_CATEGORY.get(prefix)
    if not category:
        raise HTTPException(status_code=400, detail="Invalid artifact ID prefix")
        
    # Prevent path traversal
    normalized_path = os.path.normpath(file_path)
    if normalized_path.startswith("..") or os.path.isabs(normalized_path):
        raise HTTPException(status_code=403, detail="Invalid file path")
        
    full_path = os.path.join(task.env_folder, ".ai-scientist-db", category, artifact_id, normalized_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(full_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
