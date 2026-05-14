# Per-task agent reuse: follow-up notes

Temporary notes (delete once the follow-up PR lands). Captures whether
it's feasible to reuse one interactive `mngr` agent across all of a task's
steps via `mngr message` rather than creating a fresh agent per step.

Filled in while implementing the runner migration; cites file:line so the
follow-up PR can start from code-grounded specifics.

## 1. Can `mngr message` drive successive turns on one agent?

Yes. `mngr message <agent> --message-file <path>` (see
`libs/mngr/imbue/mngr/cli/message.py:94-170`) sends the message into the
agent's tmux session and returns immediately. It does **not** block until
the agent finishes the resulting turn, so the reuse path needs the same
`mngr event --follow` + `mngr wait --state WAITING` dance the per-step
runner already uses. Same three primitives, minus the per-step
`mngr create` / `mngr stop`.

The agent stays in `RUNNING` between turns; subsequent `mngr message`
calls land in the live conversation, so prior turns' tool results and
assistant context carry over for free.

## 2. What makes each step independent today

The orchestrator was written assuming each step is a fresh agent. These
are the things that have to change before reuse works:

- **JSON result parsing is scoped to "everything in the transcript".**
  `MngrAgentRunner._read_assistant_text` (in
  `orchestrator/agents/mngr_runner.py`) reads the whole common transcript
  and concatenates every assistant text block. Reuse needs to scope this
  to "events emitted since this step's `mngr message`" — e.g. by snapshotting
  the last event_id before sending the message and slicing from there.
- **`Step.agent_name` is per-step.** Stored on `models.py:Step` as the
  unique mngr agent name. With reuse, every step in a task shares the
  same agent name; either keep it per-step (redundant info) or move it
  to `Task` and add a per-step `start_event_id` for transcript slicing.
- **Per-step `tx_id`.** `_run_step_core` at
  `orchestrator/orchestrator.py:218` mints a fresh `tx_{uuid.uuid4().hex}`
  per step and commits the context_manager transaction on success
  (`orchestrator/orchestrator.py:250`). The agent reads it via the
  `CONTEXT_TRANSACTION_ID` env var, which is baked in at `mngr create`
  time. With one long-lived agent the env var is fixed at the start, so
  reuse needs the orchestrator to bake the tx_id into the per-step
  prompt and have skills pick it up from there instead.
- **Pause/resume.** `state.cancel_task_process` runs `mngr stop` on each
  registered agent name. Same code still works under reuse, but `mngr
  stop` now halts the whole task. Resume becomes `mngr start <agent>`,
  then continue the conversation; the orchestrator has to remember which
  step was in flight.
- **`WeightedSemaphore`.** `orchestrator/orchestrator.py:20-52` caps
  concurrent *steps* per task. A single reused agent can only do one
  turn at a time — see Section 3.

## 3. Parallel steps within a task

`AI_SCIENTIST_MAX_CONCURRENCY_PER_TASK` defaults to 3
(`orchestrator/orchestrator.py:15-17`). Two parallel patterns in the
codebase:

- `develop_theory_linear.py:80-117` runs `literature-review` and
  `explore` concurrently via `threading.Thread`.
- `develop_theory.py` fans out multiple theories in parallel.

A single reused agent serializes turns. Options:

1. **Serialize parallel steps onto the shared agent.** Loses wall-clock
   parallelism but maximizes context reuse. For `literature-review` and
   `explore` this is probably fine — they're independent prep work
   that has to converge before `write-theory` anyway.
2. **N agents per task** (pool). Preserves parallelism, but the reuse
   benefit becomes partial since steps may land on agents that haven't
   seen the relevant prior context.

Recommendation: option 1. The parallelism that matters most for
ai-scientist is across tasks, not within one. Repurpose
`WeightedSemaphore` to cap concurrent *tasks* instead of concurrent
steps within a task.

## 4. Multi-turn steps inside a single workflow step

Some workflow steps drive multiple model turns internally (e.g. `swarm`
fans out to in-process subagents via Claude Code's Task tool; `explore`
calls `/swarm`). From mngr's perspective they're still one step — one
`mngr wait` for the outer agent's `WAITING`. But:

- The agent can stay in `RUNNING` for minutes-to-hours. Today's
  `_WAIT_TIMEOUT_SECONDS = 60 * 60` already accounts for this.
- "Step done" must be measured by end-of-turn signal, not intermediate
  WAITING blips during multi-skill cascades. The existing runner already
  polls for the `stop_reason == "end_turn"` marker; reuse inherits that.

## 5. Sub-skills and external claude/gemini invocations

`/swarm` and `/explore` use Claude Code's internal Task / subagent
feature — they fan out *within one `claude` process*, not by spawning
separate `claude -p` subprocesses from Python. Verified by grepping
`src/` for non-runner code that shells out to `claude` / `gemini`:

```
$ grep -rn 'subprocess.Popen\|claude -p\|gemini -p' --include='*.py' src/
src/run_experiment.py:62          process = subprocess.Popen([sys.executable, ...])
src/orchestrator/agents/mngr_runner.py:189   self._spawn_event_follower(...)
```

Only matches are `run_experiment.py` (runs user-experiment Python
scripts, not LLM agents) and the runner itself. So reuse doesn't need
swarm-specific machinery; it just needs to tolerate one step producing
one very long multi-turn run.

## 6. Concrete migration sketch

Minimum orchestrator changes:

1. `Task.agent_name: Optional[str]` on `models.py`.
2. Before running the workflow, `_orchestrate_task` calls
   `_ensure_task_agent(task)` which does `mngr create` once and stashes
   the name in `task.agent_name`. Idempotent: if the name is set and
   the agent is RUNNING / WAITING, reuse; if STOPPED, `mngr start` it.
3. `_run_step_core` calls `runner.send_step(task.agent_name, prompt,
   ...)` instead of constructing a fresh runner. The send method runs
   `mngr message` → event-follow → `mngr wait` → JSON-parse against the
   existing agent.
4. `Step.agent_name = task.agent_name` for every step; add
   `Step.start_event_id` for transcript slicing.
5. `cancel_task_process` calls `mngr stop <task.agent_name>` and marks
   the task PAUSED. Resume becomes `mngr start <task.agent_name>` then
   retry the in-flight step.
6. Repurpose `WeightedSemaphore` to per-task concurrency.
7. Collapse the `threading.Thread` fan-out in
   `develop_theory_linear.py:80-117` to sequential calls.

## 7. Open questions

- **How does a multi-turn task handle context window pressure?** Long
  ai-scientist tasks span many skill invocations. The shared agent's
  conversation grows monotonically. Plan for context management
  (summarize-and-restart? structured `/clear` at step boundaries?)
  before merging the reuse PR.
- **What does an interrupted multi-turn skill look like to the reused
  agent?** If `mngr stop` halts mid-`/swarm` and the agent is later
  restarted, does Claude pick up where it left off, or does the
  conversation end up in an inconsistent state where subagent results
  never come back?
- **Does `mngr message` cleanly interleave with `mngr connect`?** If a
  user is `mngr connect`-ed to the shared agent and the orchestrator
  fires a `mngr message`, does the user see the message arrive in
  their tmux pane?
- **`mngr_gemini` symmetry.** Confirm `mngr_gemini` exposes the same
  `mngr message` semantics for its interactive `gemini` agent type.
