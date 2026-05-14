# Per-task agent reuse: migration notes

This document is the deliverable of the mngr-migration PR: a code-grounded
input for a follow-up PR that would replace today's "fresh mngr agent per
step" pattern with "one mngr agent per task, reused across steps via
`mngr message`". It is **not** a design doc for changes proposed in this PR.

It was filled in while implementing the runner migration, citing
`file:line` for every claim.

## 1. What re-priming happens today

Every `mngr create` for a step starts a fresh interactive `claude` agent.
The agent's prompt budget gets re-spent on the same standing context per
step:

- **`_ADDITIONAL_SYSTEM_PROMPT`** at
  `orchestrator/agents/claude.py:7`, appended via `--append-system-prompt`
  on the trailing args of every `mngr create`. Short (~70 words), but
  paid every time.
- **The skill's full SKILL.md content.** Each prompt in
  `orchestrator/prompts.py` says `Please run the <foo> skill ...`, which
  is a slash-command invocation. The skill body in
  `claude_skills/skills/<foo>/SKILL.md` is loaded into the model context
  on first use of the skill in that conversation. Across steps, the same
  cluster of skills (`literature-review`, `explore`, `write-theory`,
  `review-theory`, `refine-theory`, `score-theories`,
  `falsify-hypothesis`, `suggest-expansions`, `expand-theory`,
  `polish-theory`) recurs. `wc -l claude_skills/skills/*/SKILL.md`
  reports `1587` total lines across 25 skills.
- **The phenomenon** (`task.workflow_inputs["phenomenon"]`) is repeated
  verbatim into nearly every step's prompt — see
  `orchestrator/workflows/develop_theory_linear.py:93,107`,
  `orchestrator/prompts.py:8,18,128`. For a long phenomenon description
  this is a non-trivial per-step tax.
- **IDs from prior steps** (`exploration_id`, `lit_review_id`,
  `theory_id`, `review_id`) are passed by reference in the prompt. With
  reuse, the agent would already know what each ID denotes from the
  conversation history rather than re-resolving it through the
  `context_manager` DB.
- **Home-directory sync.** `mngr_claude` syncs `~/.claude/` settings,
  Skills, and slash commands on every `mngr create`. With reuse this
  cost is paid once per task instead of per step.

Order-of-magnitude: even a small step prompt is a few hundred tokens
(`get_review_theory_prompt` at `orchestrator/prompts.py:24-28`). Add a
~3000-line skill body if the skill hasn't been loaded yet, plus the
phenomenon, plus the system prompt. With prompt caching this overhead
is partly amortized within a single `claude` session, but completely
re-paid across separate sessions — which is exactly what reuse would
fix.

## 2. What makes each step independent today

The orchestrator was written assuming each step is a fresh agent. Every
listed item is a "thing that has to change before reuse works":

- **JSON result parsing happens per step.** Every prompt ends with
  "return ONLY a JSON object with the key '...'", and
  `MngrAgentRunner.run` (in `orchestrator/agents/mngr_runner.py`)
  blocks on `mngr wait --state WAITING ...` then runs
  `parse_json_result` on the assistant text accumulated since the
  prompt was sent. Reuse needs a way to scope "the assistant text for
  *this* step" out of a continuously-growing transcript — likely
  by recording the timestamp / event-id at which the step's prompt
  was sent and slicing the event stream from there.
- **`Step.session_id` is per-step** (`orchestrator/models.py:23-32`).
  It currently stores the unique mngr agent name. Reuse changes its
  meaning to "the agent name shared across all steps of this task"
  — which is fine semantically, but most of the dashboard's per-step
  affordances (e.g. "click step → see its agent") collapse to one
  shared agent across every step.
- **Per-step `tx_id`.** `_run_step_core` at
  `orchestrator/orchestrator.py:218` creates a fresh
  `tx_{uuid.uuid4().hex}` for each step and commits the
  context_manager transaction on success
  (`orchestrator/orchestrator.py:250`). The agent reads this via the
  `CONTEXT_TRANSACTION_ID` env var. With reuse, the agent's
  environment is set once at create time but the tx_id changes per
  step — so reuse needs a way to *update* the env var mid-conversation
  (or the orchestrator needs to bake the tx_id into the per-step
  prompt and have the skill pick it up there).
- **Pause / resume code path.** `state.cancel_task_process` (in the
  rewritten `orchestrator/state.py`) iterates `_running_agents[task_id]`
  and runs `mngr stop <agent>` on each. With reuse there is one agent
  per task; the same code still works but `mngr stop` becomes more
  destructive — stopping the shared agent halts all remaining steps. To
  preserve "pause this task and resume later", reuse needs `mngr stop`
  → later `mngr start` → continue the conversation, which is supported
  by interactive agents (the work_dir and transcript are preserved) but
  needs the orchestrator to remember which step was in flight when
  paused.
- **`WeightedSemaphore` weighting.** `WeightedSemaphore` at
  `orchestrator/orchestrator.py:20-52` caps concurrent steps per task
  at `MAX_CONCURRENCY_PER_TASK` (default 3). It exists because today
  N concurrent agents can run steps in parallel for one task. Reuse
  breaks this — a single agent can only do one turn at a time. See
  Section 3.
- **Failure semantics.** Today, a failed step leaves a STOPPED agent
  with its full transcript on disk; the next step gets a fresh agent
  unaffected by the prior failure. With reuse, a failed turn corrupts
  the shared conversation state, and the orchestrator either retries
  in-place (rolling the dice on a confused model) or has to drop and
  recreate the agent (defeating the reuse).

## 3. Reuse vs. parallel-steps-per-task

`AI_SCIENTIST_MAX_CONCURRENCY_PER_TASK` defaults to 3 (see
`orchestrator/orchestrator.py:15-17`). The two parallel patterns in the
codebase:

- `develop_theory_linear.py:80-117` runs `literature-review` and
  `explore` concurrently for the same task using `threading.Thread`.
- `develop_theory.py` (not shown above but follows the same pattern)
  fans out multiple theories in parallel.

A single reused mngr agent serializes turns. Two options:

1. **Serialize parallel steps** onto the one shared agent. Loses
   wall-clock parallelism but maximizes context reuse. For
   `literature-review` and `explore` this is probably fine — they're
   independent prep work that needs to converge before `write-theory`.
2. **N agents per task**, one per parallelism slot. Pool them: when a
   parallel block needs M agents, lease M from the per-task pool;
   when serial steps run, return them. Preserves parallelism but the
   per-agent context becomes a function of which slot served which
   step, so reuse benefit is partial.

**Recommendation: option 1**, serial within a task, with the
`WeightedSemaphore` repurposed to "max concurrent *tasks*" instead of
"max concurrent steps within a task". The parallelism that matters
most for ai-scientist is across tasks, not within one.

## 4. Workflow-step boundaries vs. conversation turns

A "step" today is a single `claude` process. With `--include-partial-
messages` off it's also one assistant turn — `MngrAgentRunner` waits
for `WAITING` and reads the latest assistant text. But several skills
internally drive **multiple turns** that the orchestrator currently
sees as one step:

- `swarm` (`claude_skills/skills/swarm/SKILL.md`) fans out to N
  in-process subagents via Claude Code's Task tool, each of which is
  itself a multi-turn conversation. From ai-scientist's perspective
  this is still one mngr-managed step, but the parent claude process
  is *waiting on its subagents* for a long time.
- `explore` invokes `/swarm` (per
  `claude_skills/skills/explore/SKILL.md`).
- `review-theory` and other "multi-skill" skills cascade.

For the per-task reuse model, this matters because:

- Some "steps" are actually long multi-turn processes that take
  minutes-to-hours. Reuse must tolerate the agent staying in `RUNNING`
  for that whole time, then transitioning to `WAITING` once. The current
  `_WAIT_TIMEOUT_SECONDS = 60 * 60` in `mngr_runner.py` already accounts
  for this, but the per-task reuse path needs to be careful that "step
  done" is measured by the model's final-message-then-WAITING signal,
  not by intermediate WAITING blips inside a multi-skill cascade.
- Mngr's notion of WAITING is "the agent is at end-of-turn". So as long
  as Claude doesn't hand control back to the user mid-skill (it
  shouldn't, since these are slash-command invocations that run to
  completion), this matches what we need.

## 5. The `mngr message` contract

`mngr message <agent> "<prompt>"` (see
`libs/mngr/imbue/mngr/cli/message.py:94-170` and
`libs/mngr/imbue/mngr/api/message.py`) **sends and returns** — it
delivers the message via the agent's tmux session and exits as soon
as the message has been written. It does **not** block until the
agent finishes the resulting turn.

So the per-task reuse path mirrors today's per-step runner shape:

```
mngr message <agent> --message-file <prompt>
mngr event <agent> --source claude/common_transcript --follow --format jsonl   # background
mngr wait <agent> --state WAITING --state DONE --timeout <secs>                # blocking
```

Same three primitives the runner already uses, minus `mngr create` /
`mngr stop` per step. The per-step orchestration code (event-follower
thread + JSON-result parser + status callbacks) ports almost
verbatim — only the agent name is now task-scoped instead of
step-scoped.

## 6. Sub-skills and sub-agents

`/swarm` and `/explore` use **Claude Code's internal Task / subagent
feature** — they fan out within one `claude` process. They are *not*
spawned as separate `claude -p` subprocesses from Python.

Verified by re-grepping `src/` for any non-runner code that shells out
to `claude` / `gemini`:

```
$ grep -rn 'subprocess.Popen\|claude -p\|gemini -p' --include='*.py' src/
src/run_experiment.py:62          process = subprocess.Popen([sys.executable, ...])
src/orchestrator/agents/mngr_runner.py:189   self._spawn_event_follower(...)
```

Only matches are `run_experiment.py` (runs Python user-experiment
scripts, not LLM agents) and the runner itself.

For the reuse PR, the implication is: no swarm-specific machinery
needed, but the reuse loop must tolerate a single "step" producing one
very long multi-turn run.

## 7. Concrete migration sketch

Minimal orchestrator change:

1. Add `Task.agent_name: Optional[str]` to `models.py` — the shared
   per-task mngr agent.
2. In `orchestrator.py:_orchestrate_task`, before running the
   workflow: call a new `_ensure_task_agent(task)` that does
   `mngr create` once with `--type claude/gemini` and stashes the
   resulting name in `task.agent_name`. Idempotent: if `task.agent_name`
   is set and `mngr list` shows the agent in `RUNNING` / `WAITING`,
   reuse; if `STOPPED`, `mngr start <agent>` first.
3. `_run_step_core` no longer instantiates a fresh runner. Instead,
   call a new `runner.send_step(task.agent_name, prompt, ...)` that
   runs the `mngr message` → event-follow → `mngr wait` → JSON-parse
   sequence against the existing agent.
4. `Step.session_id` becomes `task.agent_name` for every step, plus a
   per-step `event_anchor: str` recording the event_id from which to
   slice the transcript for parsing. Stored alongside `inputs`.
5. `cancel_task_process` calls `mngr stop <task.agent_name>` and
   marks the task PAUSED. Resume becomes `mngr start <task.agent_name>`
   then retry the in-flight step.
6. Drop `WeightedSemaphore` usage at the per-step level; replace with
   a global per-task lock so steps in one task serialize.
7. Workflow files that today use `threading.Thread` for parallel
   steps (e.g. `develop_theory_linear.py:80-117`) collapse to
   sequential calls.

## 8. Open questions for the follow-up PR

- **Does prompt caching across `mngr message` calls within one
  conversation give us most of the win without true reuse?** If
  Anthropic's prompt cache has a >5min TTL covering the SKILL.md +
  system-prompt content, then per-step `mngr create` is wasting only
  cache-cold tokens, not the full prompt. Worth measuring before
  committing to the reuse PR.
- **What does an interrupted multi-turn skill look like to the
  reused agent?** If `mngr stop` halts mid-`/swarm` and the agent is
  later restarted, does Claude pick up where it left off, or does the
  conversation end up in an inconsistent state where the swarm's
  subagent results never came back?
- **Per-task token budget growth.** A long-lived task accumulates
  conversation history. Eventually the model context fills. Plan for
  context-management (summarize-and-restart? structured `/clear` at
  step boundaries?) before merging the reuse PR.
- **Does `mngr message` cleanly interleave with `mngr connect`?** If a
  user is `mngr connect`-ed to the shared agent and the orchestrator
  fires a `mngr message`, does the user see the message arrive in
  their tmux pane? (Probably yes — same tmux session — but worth
  verifying.)
- **`mngr_gemini` symmetry.** This whole sketch assumes mngr_gemini
  exposes the same `mngr message` semantics for its interactive
  `gemini` agent type. Confirm before designing.
