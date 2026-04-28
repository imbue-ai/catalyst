import threading
import uuid
import os
from typing import List, Any, Dict
from .models import Task, Step, TaskStatus, StepStatus
from .state import update_task, get_task, get_task_lock
from .agents import get_agent_runner
from .workflows import get_workflow
from .addons import get_addon_handler

def start_task(task: Task):
    print(f"[ORCHESTRATOR] Starting task {task.id[:8]}: {task.workflow_inputs.get('summary', '')[:50]}...")
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
        print(f"[ORCHESTRATOR] Unknown workflow: {task.workflow_name}")
        task.status = TaskStatus.FAILED
        update_task(task)
        return

    is_resume = task.status in [TaskStatus.PAUSED, TaskStatus.FAILED]
    print(f"[ORCHESTRATOR] Orchestrating task {task_id[:8]} via {workflow.name} (Resume: {is_resume})")
    task.status = TaskStatus.RUNNING
    update_task(task)

    try:
        def run_step_wrapper(t, stage, prompt):
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
        print(f"[ORCHESTRATOR] Task {task_id[:8]} COMPLETED successfully.")
        update_task(task)

    except Exception as e:
        # Check if it was paused
        updated_task = get_task(task_id)
        if updated_task and updated_task.status == TaskStatus.PAUSED:
            print(f"[ORCHESTRATOR] Task {task_id[:8]} PAUSED.")
            return
            
        print(f"[ORCHESTRATOR] Task {task_id[:8]} FAILED: {str(e)}")
        task.status = TaskStatus.FAILED
        if task.steps and task.steps[-1].status == StepStatus.RUNNING:
            task.steps[-1].error = str(e)
            task.steps[-1].status = StepStatus.FAILED
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
            step = existing_step
            step.status = StepStatus.RUNNING
            step.error = None
        else:
            step = Step(stage=stage, status=StepStatus.RUNNING, inputs={"prompt": prompt})
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

    output, session_id, error = runner.run(
        task_id=task.id,
        prompt=prompt,
        env_folder=task.env_folder,
        db_path=task.db_path,
        model=task.model,
        on_session_id=on_sid,
        on_status=on_status
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

        step.status = StepStatus.COMPLETED
        step.outputs = output
        update_task(task)
        return output
