import uuid
import os
import shutil
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from orchestrator.models import Task, TaskStatus
from orchestrator.state import get_tasks, get_task, add_task, update_task, cancel_task_process, delete_task, initialize_state
from orchestrator.orchestrator import start_task

app = FastAPI(title="AI Scientist Orchestrator")

# Initialize state on startup (move RUNNING to PAUSED)
initialize_state()

# Enable CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class CreateTaskRequest(BaseModel):
    phenomenon: str
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

    task_id = str(uuid.uuid4())
    # Generate unique DB path inside env_folder
    db_name = f".ai-scientist-db_{task_id[:8]}"
    db_path = os.path.join(req.env_folder, db_name)
    
    task = Task(
        id=task_id,
        phenomenon=req.phenomenon,
        env_folder=req.env_folder,
        framework=req.framework,
        model=req.model,
        db_path=db_path,
        status=TaskStatus.PENDING,
        steps=[]
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
