# Per-task agent reuse: follow-up notes

Temporary notes (delete once the follow-up PR lands). Captures whether
it's feasible to reuse one interactive `mngr` agent across all of a task's
steps via `mngr message` rather than creating a fresh agent per step.

Filled in while implementing the runner migration; cites file:line so the
follow-up PR can start from code-grounded specifics.

## 1. Can `mngr message` drive successive turns on one agent?

Yes -- and we've already partially proved it. This PR ships
`MngrAgentRunner.resume_in_place()` (in
`orchestrator/agents/mngr_runner.py`), which on pause + retry calls
`mngr start <agent>` + `mngr message <agent> --message-file
<"Continue where you left off.">` against the existing agent and
then runs the same wait + harvest the fresh-create path uses (the
shared `_wait_and_harvest` helper). The Stage B-Resume smoke
(`scripts/smoke_test_resume_in_place.py`) verifies the resumed turn
reuses the same `session_id` and produces parseable JSON. So
`mngr message` driving a successive turn on a kept-alive agent is
not theoretical anymore -- the full-reuse PR can just extend that
path to "every step, not just resume."

Two caveats from the actual implementation:

* `mngr message` returns once the message is delivered to the tmux
  session, not when the resulting turn finishes. Wait + harvest is
  still needed (event-follow for the `turn_end` Stop-hook event,
  parallel `mngr wait --state STOPPED` for cancel responsiveness).
* `_read_assistant_text` currently reads the WHOLE common transcript.
  In a multi-step reuse world it would need to scope to "events
  emitted since this step's `mngr message`" (see Section 2 below).

## 2. What makes each step independent today

The orchestrator was written assuming each step is a fresh agent. These
are the things that have to change before full reuse works:

- **JSON result parsing is scoped to "everything in the transcript".**
  `MngrAgentRunner._read_assistant_text` (in
  `orchestrator/agents/mngr_runner.py`) reads the whole common transcript
  and concatenates every assistant text block. Today (per-step
  agents) that's fine because the transcript is single-step. Once one
  agent serves multiple steps, the read needs to scope to "events
  emitted since this step's `mngr message`" -- snapshot the last
  event_id before sending the message, then slice from there.
- **`Step.session_id` is per-step.** Stored on `models.py:Step` as the
  unique mngr agent name. With reuse, every step in a task shares the
  same agent name; either keep it per-step (redundant info) or move it
  to `Task` and add a per-step `start_event_id` for transcript slicing.
- **Per-step `tx_id` -- now persisted.** This PR added `Step.tx_id`
  (`models.py`) and made `_run_step_core` reuse it across re-runs, so
  resume-in-place doesn't orphan context_manager's staged writes
  (`CONTEXT_TRANSACTION_ID` is baked into the agent's env file at
  `mngr create` time and never changes for that agent's lifetime). For
  the FULL reuse model -- one long-lived agent across all steps -- this
  approach breaks down: the env var can't be re-baked per step. The
  follow-up needs to either (a) bake the tx_id into the per-step prompt
  and have skills read it from there, or (b) move the tx_id into a file
  the skills already read on each turn.
- **Pause/resume -- partially implemented.** This PR ships
  `runner.resume_in_place(agent_name, ...)` (`mngr start` + `mngr
  message <"Continue where you left off.">`) and wires the orchestrator
  to call it whenever `step.session_id` is set and the framework is
  `mngr-*`. With unrecoverable failure (agent destroyed out-of-band) it
  returns a `"resume_unrecoverable:"` error and the orchestrator falls
  back to fresh `run()`. Full reuse inherits this exact mechanism --
  just call it on EVERY step after the first, not only on retries.
- **`WeightedSemaphore`.** `orchestrator/orchestrator.py:20-52` caps
  concurrent *steps* per task. A single reused agent can only do one
  turn at a time -- see Section 3.

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

What this PR already provides (free for the follow-up to build on):

* `MngrAgentRunner.resume_in_place(agent_name, ...)` --
  `mngr start` + `mngr message` against an existing agent, then wait
  for `turn_end`. Returns `"resume_unrecoverable:"` if `mngr start`
  fails so callers can recover. Already used by `_run_step_core`
  on retries / pause-resume.
* `Step.tx_id` persistence so a re-run of the same step keeps the
  same `CONTEXT_TRANSACTION_ID`. (Full reuse needs to extend this --
  see Section 2 caveat.)
* Pause is prompt-responsive: `_wait_for_turn_end` runs `mngr event
  --follow` and `mngr wait --state STOPPED` in parallel, so the
  reused-agent path inherits the same Pause UX.

Minimum additional orchestrator changes for the full per-task reuse:

1. `Task.session_id: Optional[str]` on `models.py` (the task's
   long-lived mngr agent name; distinct from `Step.session_id` which
   is per-step today).
2. Before running the workflow, `_orchestrate_task` calls
   `_ensure_task_agent(task)`: if `task.session_id` is set and the
   agent is RUNNING / WAITING, reuse; if STOPPED, `mngr start` it;
   else `mngr create` once and stash the name. Idempotent.
3. `_run_step_core` calls a new
   `runner.send_step(task.session_id, prompt, ...)` -- essentially
   `resume_in_place` but with the step's actual prompt instead of
   "Continue where you left off." Reuses the
   `_wait_and_harvest` helper already factored out for resume.
4. `Step.session_id = task.session_id` for every step; add
   `Step.start_event_id` (the event_id at the time `mngr message`
   fired) so `_read_assistant_text` can slice to events emitted by
   THIS step's turn, not the whole accumulated transcript.
5. Decide the tx_id story: either bake into the per-step prompt
   (skills read it from there) or write to a file the skills already
   poll. The current "env var" approach can't work for a long-lived
   agent.
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
  agent?** Partially answered by Stage B-Resume: if `mngr stop` halts
  the agent between turns (after subagents returned, before parent
  emitted JSON), `mngr start` + "Continue where you left off." picks
  up cleanly and the parent re-emits the final JSON. Still unverified:
  what happens if the stop fires WHILE subagents are mid-execution --
  do their in-process Task contexts survive the tmux pause, or does
  claude come back to a torn state?
- **Does `mngr message` cleanly interleave with `mngr connect`?** If a
  user is `mngr connect`-ed to the shared agent and the orchestrator
  fires a `mngr message`, does the user see the message arrive in
  their tmux pane?
- **`mngr_gemini` symmetry.** Confirm `mngr_gemini` exposes the same
  `mngr message` semantics for its interactive `gemini` agent type.
