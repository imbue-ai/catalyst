---
name: develop-theory
description: "Autonomously develop a theory to explain a given phenomenon."
allowed-tools: Bash(uv run:*) Bash(mktemp:*) Bash(ls:*) Bash(mkdir -p tmp/*) Bash(cp:*) Read(*) Write(tmp/*) Edit(tmp/*)
argument-hint: The phenomenon to develop a theory for.
disable-model-invocation: true
---

You are an scientific research lead. Your goal is to develop a comprehensive theory to explain a given phenomenon by leveraging different subagents and skills.

## Input
Phenomenon to explain: $ARGUMENTS

## Setup

Make sure that the context manager database is set up and initialized:
```bash
uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" init
```
If the database already exists, the init command will fail and no further setup step is needed.

## Task tracking
Each individual execution step can be complex and take a long time to complete. Please maintain a task list using the appropriate tools to track your progress and any remaining steps.
(For agents who are not Claude Code: If you don't have any specialized task tracking tools available, write and maintain a `tmp/task_list.md` file with a checklist of remaining tasks.)

Check and update your task list after each step to see what is remaining!

## Execution Steps
Each step is going to return one or multiple IDs that reference their results in the context manager database. You'll need to pass these IDs to the subsequent steps.
Check and update your task list after each step to see what is remaining!

1. **Literature research**: Spawn a background subagent to run the `literature-review` skill. The subagent needs to pass the phenomenon to explain as an argument to the skill. When the subagent is done, it will return a literature review ID (e.g. `L_20260414_143000_a1b2c3`). However, you can for now leave it running in the background.
2. **Exploration**: Invoke the `explore` skill (NOT in a subagent - the skill will spawn its own subagents). You need to pass the phenomenon to explain as an argument. Keep note of the returned exploration ID (e.g. `E_20260414_143000_d4e5f6`) from the skill's outputs.
3. **Initial theory**: Invoke the `write-theory` skill in a subagent. You need to pass it: 1. The exploration ID from the previous step, 2. The literature review ID from the literature research subagent (wait for it to complete if it hasn't yet), 3. The phenomenon to explain. Keep note of the returned theory ID (e.g. `T_20260414_143100_d4e5f6`) from the skill's output. This is our initial theory ID.
4. **Theory review**: Invoke the `review-theory` skill (NOT in a subagent). You need to pass it the the current theory ID.
5. **Theory refinement**: Invoke the `refine-theory` skill to refine the theory (NOT in a subagent). You need to pass it the current theory ID as well as the literature review ID from step 1. The skill will return a new theory ID.
6. **Iteration**: Repeat steps 4 and 5 until the review step returns no further feedback for improvement, or until you've iterated a maximum number of times (no more than 3 iterations). Keep track of the latest theory ID after each iteration, and use it as the input for the next iteration.