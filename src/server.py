import uuid
import os
import shutil
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize state on startup (move RUNNING to PAUSED)
    initialize_state()
    yield
    # Clean up processes on shutdown
    print("[SERVER] Shutting down, cleaning up processes...")
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
    env_folder: str
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
    # Verify environment folder exists
    abs_env_folder = os.path.abspath(req.env_folder)
    if not os.path.exists(abs_env_folder) or not os.path.isdir(abs_env_folder):
        raise HTTPException(status_code=400, detail=f"Environment folder does not exist: {req.env_folder}")

    # Inject summary into workflow_inputs
    inputs = dict(req.workflow_inputs)
    summary_candidate = inputs.get("phenomenon") or inputs.get("idea") or ""
    inputs["summary"] = summary_candidate

    task_id = str(uuid.uuid4())
    # Generate unique DB path inside env_folder
    db_name = f".ai-scientist-db_{task_id[:8]}"
    db_path = os.path.join(req.env_folder, db_name)
    
    task = Task(
        id=task_id,
        workflow_inputs=inputs,
        env_folder=req.env_folder,
        framework=req.framework,
        model=req.model,
        db_path=db_path,
        status=TaskStatus.PENDING,
        steps=[],
        workflow_name=req.workflow_name
    )
    
    add_task(task)
    start_task(task)
    return task

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
    if os.path.exists(task.db_path):
        try:
            if os.path.isdir(task.db_path):
                shutil.rmtree(task.db_path)
            else:
                os.remove(task.db_path)
        except Exception as e:
            print(f"Error deleting db_path {task.db_path}: {e}")

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
        
    file_path = os.path.join(task.db_path, category, artifact_id, md_filename)
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
        
    full_path = os.path.join(task.db_path, category, artifact_id, normalized_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(full_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
