import threading
import uuid
import os
from typing import List, Any
from concurrent.futures import ThreadPoolExecutor
from .models import Task, Step, TaskStatus, StepStatus
from .state import update_task, get_task, get_task_lock
from .agent_runner import run_agent

def start_task(task: Task):
    thread = threading.Thread(target=_orchestrate_task, args=(task.id,))
    thread.daemon = True
    thread.start()

def _orchestrate_task(task_id: str):
    task = get_task(task_id)
    if not task:
        return

    # If already running, don't start another one
    if task.status == TaskStatus.RUNNING:
        return

    is_resume = task.status in [TaskStatus.PAUSED, TaskStatus.FAILED]
    task.status = TaskStatus.RUNNING
    update_task(task)

    try:
        # Step 0: Summarized Title
        if not task.title:
            title_data = _run_step(
                task,
                "summarize-title",
                f"Please provide a very short, summarized title (maximum 5 words) for the following research phenomenon: {task.phenomenon}. "
                "Return a JSON object with the key 'title'."
            )
            if title_data and isinstance(title_data, dict):
                task.title = title_data.get("title")
                update_task(task)

        # Helper to find if a step was already completed
        def get_step_output(stage_prefix: str):
            for s in task.steps:
                if s.stage.startswith(stage_prefix) and s.status == StepStatus.COMPLETED:
                    return s.outputs
            return None

        # Helper to get lit review id
        def get_lit_id():
            out = get_step_output("literature-review")
            return out.get("literature_review_id") if out else None

        # Step 1 & 2: Literature Review and Exploration in Parallel
        lit_review_id = get_lit_id()
        exploration_data = get_step_output("explore")
        exploration_id = exploration_data.get("exploration_id") if exploration_data else None

        if not lit_review_id or not exploration_id:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = []
                if not lit_review_id:
                    futures.append(executor.submit(
                        _run_step, task, "literature-review",
                        f"Please run the literature-review skill for the following phenomenon: {task.phenomenon}. "
                        "When you are done, return a JSON object with the key 'literature_review_id'."
                    ))
                if not exploration_id:
                    futures.append(executor.submit(
                        _run_step, task, "explore",
                        f"Please run the explore skill for the following phenomenon: {task.phenomenon}. "
                        "When you are done, return a JSON object with the key 'exploration_id'."
                    ))
                
                results = [f.result() for f in futures]
                
                # Update IDs from results
                for res in results:
                    if res and isinstance(res, dict):
                        if "literature_review_id" in res:
                            lit_review_id = res["literature_review_id"]
                        if "exploration_id" in res:
                            exploration_id = res["exploration_id"]

        if not lit_review_id or not exploration_id: return

        # Step 3: Initial Theory
        theory_data = get_step_output("write-theory")
        theory_id = theory_data.get("theory_id") if theory_data else None
        if not theory_id:
            theory_data = _run_step(
                task,
                "write-theory",
                f"Please run the write-theory skill for the following phenomenon: {task.phenomenon}. "
                f"Use exploration_id: {exploration_id} and literature_review_id: {lit_review_id}. "
                "When you are done, return a JSON object with the key 'theory_id'."
            )
            theory_id = theory_data.get("theory_id")
        if not theory_id: return

        # Step 4: Iterative Review and Refinement
        for i in range(1, 4):
            # Review
            review_data = get_step_output(f"review-theory-{i}")
            if not review_data:
                review_data = _run_step(
                    task,
                    f"review-theory-{i}",
                    f"Please run the review-theory skill for the following theory_id: {theory_id}. "
                    "When you are done, return a JSON object with the key 'review_ids' (a list of strings)."
                )
            if not review_data: break
            
            review_ids = review_data.get("review_ids", [])
            if not review_ids:
                break

            # Refine
            refine_data = get_step_output(f"refine-theory-{i}")
            if not refine_data:
                refine_data = _run_step(
                    task,
                    f"refine-theory-{i}",
                    f"Please run the refine-theory skill for the following theory_id: {theory_id}. "
                    f"Use literature_review_id: {lit_review_id}. "
                    "When you are done, return a JSON object with the keys 'theory_id' and 'major_changes' (boolean)."
                )
            if not refine_data: break
            
            theory_id = refine_data.get("theory_id")
            if not theory_id: break

        task.status = TaskStatus.COMPLETED
        update_task(task)

    except Exception as e:
        # Check if it was paused
        updated_task = get_task(task_id)
        if updated_task and updated_task.status == TaskStatus.PAUSED:
            return
            
        task.status = TaskStatus.FAILED
        if task.steps and task.steps[-1].status == StepStatus.RUNNING:
            task.steps[-1].error = str(e)
            task.steps[-1].status = StepStatus.FAILED
        update_task(task)

def _run_step(task: Task, stage: str, prompt: str) -> Any:
    # Check if we should resume a failed/cancelled step
    resume_session_id = None
    existing_step = None
    
    lock = get_task_lock(task.id)
    with lock:
        for s in task.steps:
            if s.stage == stage:
                existing_step = s
                if s.status in [StepStatus.FAILED, StepStatus.RUNNING]: # RUNNING means it was interrupted
                    resume_session_id = s.session_id
                break

        if existing_step:
            step = existing_step
            step.status = StepStatus.RUNNING
            step.error = None
            # If resuming, maybe change prompt? User said resume should use "Please resume"
            if resume_session_id:
                effective_prompt = "Please resume your previous work."
            else:
                effective_prompt = prompt
        else:
            step = Step(stage=stage, status=StepStatus.RUNNING, inputs={"prompt": prompt})
            task.steps.append(step)
            effective_prompt = prompt

        task.current_stage = stage
        update_task(task)

        def on_sid(sid):
            with lock:
                step.session_id = sid
                update_task(task)

        output, session_id, error = run_agent(
            task_id=task.id,
            framework=task.framework,
            prompt=effective_prompt,
            env_folder=task.env_folder,
            db_path=task.db_path,
            model=task.model,
            resume_session_id=resume_session_id,
            on_session_id=on_sid
        )
    # Check for pause again
    updated_task = get_task(task.id)
    
    with lock:
        if updated_task and updated_task.status == TaskStatus.PAUSED:
            step.status = StepStatus.FAILED
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
