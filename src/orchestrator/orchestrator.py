import threading
import logging
import uuid
import os
from typing import List, Any, Dict
from .models import Task, Step, TaskStatus, StepStatus, StepCategory
from .state import update_task, get_task, get_task_lock
from .agents import get_agent_runner
from .workflows import get_workflow
from .addons import get_addon_handler
from .utils import run_context_manager

logger = logging.getLogger(__name__)

MAX_CONCURRENCY_PER_TASK = int(os.environ.get("CATALYST_MAX_CONCURRENCY_PER_TASK", 3))


class WeightedSemaphore:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.available = capacity
        self.cond = threading.Condition()

    def acquire(self, weight: int = 1):
        # Prevent starvation: cap the required weight at the total capacity
        weight = min(weight, self.capacity)
        with self.cond:
            while self.available < weight:
                self.cond.wait()
            self.available -= weight

    def release(self, weight: int = 1):
        weight = min(weight, self.capacity)
        with self.cond:
            self.available += weight
            self.cond.notify_all()

    class _Context:
        def __init__(self, sem, weight):
            self.sem = sem
            self.weight = weight

        def __enter__(self):
            self.sem.acquire(self.weight)

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.sem.release(self.weight)

    def __call__(self, weight: int = 1):
        return self._Context(self, weight)


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
    lock = get_task_lock(task_id)
    with lock:
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
        semaphore = WeightedSemaphore(MAX_CONCURRENCY_PER_TASK)

        def run_step_wrapper(t, stage, prompt, category: StepCategory, cost=1):
            lock = get_task_lock(t.id)
            with lock:
                current_task = get_task(t.id)
                if current_task and current_task.status not in [
                    TaskStatus.RUNNING,
                    TaskStatus.PENDING,
                ]:
                    return {"_canceled": True}

                # Set to WAITING before acquiring semaphore
                existing_step = next(
                    (s for s in current_task.steps if s.stage == stage), None
                )
                if existing_step:
                    if existing_step.status == StepStatus.CANCELED:
                        return {"_canceled": True}
                    step = existing_step
                    step.reset()
                    step.status = StepStatus.WAITING
                else:
                    step = Step(
                        stage=stage,
                        status=StepStatus.WAITING,
                        inputs={"prompt": prompt},
                    )
                    current_task.steps.append(step)

                current_task.current_stage = stage
                current_task.workflow_structure = get_full_structure(
                    workflow, current_task
                )
                update_task(current_task)

            with semaphore(cost):
                # Double-check status after acquiring
                current_task = get_task(t.id)
                if current_task and current_task.status not in [
                    TaskStatus.RUNNING,
                    TaskStatus.PENDING,
                ]:
                    return {"_canceled": True}

                with lock:
                    # Transition to RUNNING
                    step = next(
                        (s for s in current_task.steps if s.stage == stage), None
                    )
                    if step and step.status != StepStatus.CANCELED:
                        step.status = StepStatus.RUNNING
                    update_task(current_task)

                res = _run_step_core(t, stage, prompt, category)
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


def _run_step_core(task: Task, stage: str, prompt: str, category: StepCategory) -> Any:
    # This core function assumes the step is already created and in RUNNING state
    lock = get_task_lock(task.id)
    step = None
    with lock:
        for s in task.steps:
            if s.stage == stage:
                step = s
                break

    if not step:
        raise Exception(f"Step {stage} not found in task {task.id}")

    def on_sid(sid):
        with lock:
            step.session_id = sid
            update_task(task)

    def on_status(status):
        with lock:
            step.last_status = status
            update_task(task)

    framework = task.framework
    model = task.model
    effort = task.effort

    if task.category_overrides and category in task.category_overrides:
        override = task.category_overrides[category]
        if override.framework is not None:
            framework = override.framework
        if override.model is not None:
            model = override.model
        if override.effort is not None:
            effort = override.effort

    runner = get_agent_runner(framework)
    if not runner:
        error = f"No agent runner found for framework: {framework}"
        with lock:
            step.status = StepStatus.FAILED
            step.error = error
            update_task(task)
        raise Exception(error)

    tx_id = f"tx_{uuid.uuid4().hex}"

    common_env = runner.build_common_environment_variables(
        env_folder=task.env_folder,
        tx_id=tx_id,
        theory_scoring_weights=task.theory_scoring_weights,
    )

    output, session_id, error = runner.run(
        task_id=task.id,
        prompt=prompt,
        env_folder=task.env_folder,
        stage=stage,
        common_environment_variables=common_env,
        model=model,
        effort=effort,
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
