import threading
import logging
import uuid
from typing import List, Any, Dict
from .models import Task, Step, TaskStatus, StepStatus
from .state import update_task, get_task, get_task_lock
from .agents import get_agent_runner
from .workflows import get_workflow
from .addons import get_addon_handler
from .utils import run_context_manager

logger = logging.getLogger(__name__)

MAX_CONCURRENCY_PER_TASK = 2


def start_task(task: Task):
    logger.info(
        f"[ORCHESTRATOR] Starting task {task.id[:8]}: {task.workflow_inputs.get('summary', '')[:50]}..."
    )
    thread = threading.Thread(target=_orchestrate_task, args=(task.id,))
    thread.daemon = True
    thread.start()


def get_full_structure(workflow, task: Task) -> List[Dict[str, Any]]:
    structure = workflow.get_structure(task) if workflow else []
    for i, addon in enumerate(task.addons):
        handler = get_addon_handler(addon.type)
        if handler:
            structure.append(handler.get_structure(addon, i, task))
        else:
            structure.append({"type": "step", "stage": f"addon-{addon.type}-{i}"})
    return structure


def _orchestrate_task(task_id: str):
    task = get_task(task_id)
    if not task:
        return

    # If already running, don't start another one
    if task.status == TaskStatus.RUNNING:
        return

    workflow = get_workflow(task.workflow_name)
    if not workflow:
        logger.error(f"[ORCHESTRATOR] Unknown workflow: {task.workflow_name}")
        task.status = TaskStatus.FAILED
        update_task(task)
        return

    is_resume = task.status in [TaskStatus.PAUSED, TaskStatus.FAILED]
    logger.info(
        f"[ORCHESTRATOR] Orchestrating task {task_id[:8]} via {workflow.name} (Resume: {is_resume})"
    )
    task.status = TaskStatus.RUNNING
    update_task(task)

    try:
        # Global per-task concurrency limit
        semaphore = threading.Semaphore(MAX_CONCURRENCY_PER_TASK)

        def run_step_wrapper(t, stage, prompt):
            with semaphore:
                current_task = get_task(t.id)
                if current_task and current_task.status not in [
                    TaskStatus.RUNNING,
                    TaskStatus.PENDING,
                ]:
                    return {"_canceled": True}

                res = _run_step(t, stage, prompt)
                # Update structure after each step to reflect progress
                t.workflow_structure = get_full_structure(workflow, t)
                update_task(t)
                return res

        # Initialize/Update structure before running
        task.workflow_structure = get_full_structure(workflow, task)
        update_task(task)

        workflow.run(task, run_step_wrapper)

        # Process Addons
        for i, addon in enumerate(task.addons):
            handler = get_addon_handler(addon.type)
            if not handler:
                raise Exception(f"Unknown addon type: {addon.type}")

            handler.run(task, run_step_wrapper, addon, i)

        task.status = TaskStatus.COMPLETED
        logger.info(f"[ORCHESTRATOR] Task {task_id[:8]} COMPLETED successfully.")
        update_task(task)

    except Exception as e:
        # Check if it was paused
        updated_task = get_task(task_id)
        if updated_task and updated_task.status == TaskStatus.PAUSED:
            logger.info(f"[ORCHESTRATOR] Task {task_id[:8]} PAUSED.")
            return

        logger.error(f"[ORCHESTRATOR] Task {task_id[:8]} FAILED: {str(e)}")
        task.status = TaskStatus.FAILED
        update_task(task)


def _run_step(task: Task, stage: str, prompt: str) -> Any:
    # Check if we should restart a failed/paused step
    existing_step = None

    workflow = get_workflow(task.workflow_name)

    lock = get_task_lock(task.id)
    with lock:
        for s in task.steps:
            if s.stage == stage:
                existing_step = s
                break

        if existing_step:
            if existing_step.status == StepStatus.CANCELED:
                return {"_canceled": True}
            step = existing_step
            step.status = StepStatus.RUNNING
            step.error = None
        else:
            step = Step(
                stage=stage, status=StepStatus.RUNNING, inputs={"prompt": prompt}
            )
            task.steps.append(step)

        task.current_stage = stage
        if workflow:
            task.workflow_structure = get_full_structure(workflow, task)
        update_task(task)

    def on_sid(sid):
        with lock:
            step.session_id = sid
            update_task(task)

    def on_status(status):
        with lock:
            step.last_status = status
            update_task(task)

    runner = get_agent_runner(task.framework)
    if not runner:
        error = f"No agent runner found for framework: {task.framework}"
        with lock:
            step.status = StepStatus.FAILED
            step.error = error
            update_task(task)
        raise Exception(error)

    tx_id = f"tx_{uuid.uuid4().hex}"

    output, session_id, error = runner.run(
        task_id=task.id,
        prompt=prompt,
        env_folder=task.env_folder,
        model=task.model,
        tx_id=tx_id,
        on_session_id=on_sid,
        on_status=on_status,
    )

    # Check for pause again
    updated_task = get_task(task.id)

    with lock:
        if updated_task and updated_task.status == TaskStatus.PAUSED:
            step.status = StepStatus.PAUSED
            step.error = "Paused"
            step.session_id = session_id
            update_task(task)
            raise Exception("Paused")

        step.session_id = session_id
        if error:
            step.status = StepStatus.FAILED
            step.error = error
            update_task(task)
            raise Exception(error)

    # Success: Commit the transaction
    try:
        run_context_manager(task, ["commit", tx_id])
    except Exception as commit_err:
        error_msg = f"Transaction commit failed: {commit_err}"
        logger.error(f"[ORCHESTRATOR] [{task.id[:8]}] {error_msg}")
        with lock:
            step.status = StepStatus.FAILED
            step.error = error_msg
            update_task(task)
        raise Exception(error_msg)

    with lock:
        step.status = StepStatus.COMPLETED
        step.outputs = output
        update_task(task)
        return output
