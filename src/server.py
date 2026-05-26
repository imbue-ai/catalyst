import uuid
import os
import shutil
import logging
import subprocess
import json
import io
import zipfile
import re
from fastapi import FastAPI, HTTPException, Response, File, Form, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from orchestrator.models import Task, TaskStatus
from orchestrator.state import (
    get_tasks,
    get_task,
    add_task,
    update_task,
    cancel_task_process,
    delete_task,
    initialize_state,
    shutdown_all,
)
from orchestrator.orchestrator import start_task
from orchestrator.utils import get_catalyst_path, run_context_manager
from context_manager import PREFIX_TO_CATEGORY, CATEGORY_MD_MAP, DEFAULT_DB_DIR

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


app = FastAPI(title="Catalyst Orchestrator", lifespan=lifespan)

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


@app.get("/api/templates")
def list_templates():
    templates_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "templates")
    )
    if not os.path.exists(templates_dir) or not os.path.isdir(templates_dir):
        return []

    templates = []
    for item in os.listdir(templates_dir):
        if os.path.isdir(os.path.join(templates_dir, item)):
            templates.append(item)
    return sorted(templates)


@app.post("/api/tasks", response_model=Task)
def create_task(request: str = Form(...), file: Optional[UploadFile] = File(None)):
    try:
        req_data = json.loads(request)
        req = CreateTaskRequest(**req_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request data: {e}")

    task_id = str(uuid.uuid4())

    # Generate unique target path inside configured research directory
    base_research_dir = os.path.join(get_catalyst_path(), "research")
    target_path = os.path.abspath(os.path.join(base_research_dir, f"task_{task_id[:8]}"))

    # Run create_environment.py
    cmd = ["uv", "run", "python", "create_environment.py", target_path]
    if req.template_folder:
        abs_template = os.path.abspath(req.template_folder)
        if not os.path.exists(abs_template) or not os.path.isdir(abs_template):
            raise HTTPException(
                status_code=400,
                detail=f"Template folder does not exist: {req.template_folder}",
            )
        cmd.extend(["--template", abs_template])

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create environment: {e}"
        )

    # Inject summary into workflow_inputs
    inputs = dict(req.workflow_inputs)

    if file:
        import_dir = os.path.join(target_path, "tmp", "import")
        os.makedirs(import_dir, exist_ok=True)
        if file.filename.endswith(".zip"):
            zip_path = os.path.join(import_dir, "upload.zip")
            with open(zip_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(import_dir)
            os.remove(zip_path)
            inputs["file_path"] = (
                "tmp/import (a zip archive was unpacked into this folder)"
            )
        else:
            filename = file.filename
            file_save_path = os.path.join(import_dir, filename)
            with open(file_save_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            inputs["file_path"] = f"tmp/import/{filename}"

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
        workflow_name=req.workflow_name,
    )

    add_task(task)
    start_task(task)
    return task


class CreateAddonRequest(BaseModel):
    type: str
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


@app.post("/api/tasks/{task_id}/addons", response_model=Task)
def create_addon(task_id: str, req: CreateAddonRequest):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    from orchestrator.models import Addon

    addon = Addon(
        type=req.type,
        theory_id=req.theory_id,
        theory_ids=req.theory_ids,
        direction=req.direction,
        max_refinements=req.max_refinements,
        apply_expansions=req.apply_expansions,
        evolve_iterations=req.evolve_iterations,
        num_parents=req.num_parents,
        max_streamline_prob=req.max_streamline_prob,
        write_different_prob=req.write_different_prob,
        num_extra_scores=req.num_extra_scores,
        review_id=req.review_id,
        hypothesis_title=req.hypothesis_title,
        instruction=req.instruction,
        lit_review_id=req.lit_review_id,
    )
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
        if step.status in (StepStatus.FAILED, StepStatus.PAUSED, StepStatus.PENDING, StepStatus.WAITING):
            step.status = StepStatus.CANCELED
            update_task(task)
            return {"status": "canceled"}
        else:
            raise HTTPException(
                status_code=400,
                detail="Can only cancel steps in failed, paused, pending, or waiting state",
            )
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
            if step.status in (
                StepStatus.FAILED,
                StepStatus.PAUSED,
                StepStatus.PENDING,
                StepStatus.WAITING,
            ):
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
    from orchestrator.models import StepStatus
    for step in task.steps:
        if step.status in (StepStatus.RUNNING, StepStatus.WAITING):
            step.status = StepStatus.PAUSED
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


@app.get("/api/tasks/{task_id}/theories")
def get_task_theories(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        result = run_context_manager(
            task, ["list", "--type", "theory", "--sort_by", "score", "--json"]
        )
        data = json.loads(result)
        data.reverse()
        return data
    except Exception as e:
        logger.error(f"Error running context_manager list for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve theories")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding context_manager output for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse theories")


@app.get("/api/tasks/{task_id}/reviews")
def get_task_reviews(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        result = run_context_manager(task, ["list", "--type", "review", "--json"])
        data = json.loads(result)
        data.reverse()
        return data
    except subprocess.CalledProcessError as e:
        logger.error(
            f"Error running context_manager list for task {task_id}: {e.stderr}"
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve reviews")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding context_manager output for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse reviews")


@app.get("/api/tasks/{task_id}/experiments")
def get_task_experiments(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        result = run_context_manager(task, ["list", "--type", "experiment", "--json"])
        data = json.loads(result)
        data.reverse()
        return data
    except subprocess.CalledProcessError as e:
        logger.error(
            f"Error running context_manager list for task {task_id}: {e.stderr}"
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve experiments")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding context_manager output for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse experiments")


def inject_disclaimer(content: str) -> str:
    disclaimer = "*This document has been generated by the Catalyst AI Scientist tool. It may contain mistakes, misrepresentations, or lack important citations. Please verify all claims.*"
    lines = content.split("\n")
    if not lines or not content:
        return disclaimer + "\n\n"
    if lines[0].startswith("# "):
        rest = "\n".join(lines[1:]).lstrip("\n")
        return lines[0] + "\n\n" + disclaimer + "\n\n" + rest
    return disclaimer + "\n\n" + content


@app.get("/api/tasks/{task_id}/artifacts/{artifact_id}/primary")
def get_artifact_primary(task_id: str, artifact_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    prefix = artifact_id.split("_")[0]
    category = PREFIX_TO_CATEGORY.get(prefix)
    if not category:
        raise HTTPException(status_code=400, detail="Invalid artifact ID prefix")

    md_filename = CATEGORY_MD_MAP.get(category)
    if not md_filename:
        raise HTTPException(
            status_code=500, detail="No primary markdown configured for category"
        )

    file_path = os.path.join(
        task.env_folder, DEFAULT_DB_DIR, category, artifact_id, md_filename
    )
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Artifact file not found")

    with open(file_path, "r", encoding="utf-8") as f:
        return {"content": inject_disclaimer(f.read())}


@app.get("/api/tasks/{task_id}/artifacts/{artifact_id}/files")
def list_artifact_files(task_id: str, artifact_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    prefix = artifact_id.split("_")[0]
    category = PREFIX_TO_CATEGORY.get(prefix)
    if not category:
        raise HTTPException(status_code=400, detail="Invalid artifact ID prefix")

    dir_path = os.path.join(
        task.env_folder, DEFAULT_DB_DIR, category, artifact_id
    )
    if not os.path.exists(dir_path):
        raise HTTPException(status_code=404, detail="Artifact directory not found")

    files = []
    for root, _, filenames in os.walk(dir_path):
        for f in filenames:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, dir_path)
            # Use forward slashes for consistent web paths
            files.append(rel_path.replace(os.sep, '/'))

    def sort_key(path):
        parts = path.split('/')
        return [(1 if i < len(parts) - 1 else 0, part) for i, part in enumerate(parts)]

    return sorted(files, key=sort_key)


@app.get("/api/tasks/{task_id}/artifacts/{artifact_id}/files/{file_path:path}")
def get_artifact_file(task_id: str, artifact_id: str, file_path: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    prefix = artifact_id.split("_")[0]
    category = PREFIX_TO_CATEGORY.get(prefix)
    if not category:
        raise HTTPException(status_code=400, detail="Invalid artifact ID prefix")

    # Prevent path traversal
    normalized_path = os.path.normpath(file_path)
    if normalized_path.startswith("..") or os.path.isabs(normalized_path):
        raise HTTPException(status_code=403, detail="Invalid file path")

    full_path = os.path.join(
        task.env_folder, DEFAULT_DB_DIR, category, artifact_id, normalized_path
    )
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(full_path)


@app.get("/api/tasks/{task_id}/artifacts/{artifact_id}/export")
def export_artifact(task_id: str, artifact_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    prefix = artifact_id.split("_")[0]
    category = PREFIX_TO_CATEGORY.get(prefix)
    if not category:
        raise HTTPException(status_code=400, detail="Invalid artifact ID prefix")

    md_filename = CATEGORY_MD_MAP.get(category)
    if not md_filename:
        raise HTTPException(
            status_code=500, detail="No primary markdown configured for category"
        )

    artifact_dir = os.path.join(
        task.env_folder, DEFAULT_DB_DIR, category, artifact_id
    )
    md_path = os.path.join(artifact_dir, md_filename)

    if not os.path.exists(md_path):
        raise HTTPException(status_code=404, detail="Artifact file not found")

    with open(md_path, "r", encoding="utf-8") as f:
        md_content = inject_disclaimer(f.read())

    # Extract relative images
    image_paths = []
    # Markdown ![alt](path)
    image_paths.extend(
        re.findall(r"!\[.*?\]\((?!http|/)(.*?)\)", md_content, flags=re.DOTALL)
    )
    # HTML <img src="path" />
    image_paths.extend(
        re.findall(r'<img[^>]+src=["\'](?!http|/)([^"\']+)["\']', md_content)
    )

    # Dedup and sanitize (remove anchors/queries if any)
    sanitized_paths = []
    for p in set(image_paths):
        p_clean = p.split("#")[0].split("?")[0].strip()
        if p_clean:
            sanitized_paths.append(p_clean)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # Markdown file inside folder
        zip_file.writestr(os.path.join(artifact_id, md_filename), md_content)

        # Images inside folder, preserving subpaths
        for img_rel_path in sanitized_paths:
            img_full_path = os.path.join(artifact_dir, img_rel_path)
            # Ensure it is still within artifact_dir to prevent path traversal
            if os.path.abspath(img_full_path).startswith(os.path.abspath(artifact_dir)):
                if os.path.exists(img_full_path) and os.path.isfile(img_full_path):
                    zip_file.write(
                        img_full_path, os.path.join(artifact_id, img_rel_path)
                    )

    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{artifact_id}.zip"'},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8139)
