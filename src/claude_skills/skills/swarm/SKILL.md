---
name: swarm
description: "Fan out a task to N independent agents with diverse approaches and collect all results"
allowed-tools: Read Bash Glob Grep Write Edit Agent TeamCreate TaskCreate TaskUpdate TaskList SendMessage
argument-hint: The task to swarm. Optionally specify N (default 3).
---

You are the **Swarm Coordinator**. Fan out a single task to N independent agents, each taking a distinct approach, then collect and return all results.

## Input
Task to swarm (and optionally N): $ARGUMENTS

## Workflow (Claude Code)
Use this workflow if you're Claude Code and have access to the TeamCreate, TaskCreate and SendMessage tools.

1. Decide on N agents (default 3). Before spawning, assign each agent a distinct approach — different methodology, assumptions, perspective, or tools. Name the approaches explicitly.
2. `TeamCreate` with a short descriptive `team_name`
3. `TaskCreate` one task per agent
4. Spawn all agents **in parallel** via `Agent`. In each agent's prompt: state the shared task, assign their specific approach, and list the other agents' approaches so they know to diverge. Each agent must `SendMessage` back with their result.
5. Wait for all to report back, then shut down teammates

## Workflow (other agents)
Use this workflow if you're not Claude Code.

1. Decide on N agents (default 3). Before spawning, assign each agent a distinct approach — different methodology, assumptions, perspective, or tools. Name the approaches explicitly.
2. Spawn all N subagents **in parallel**. In each agent's prompt: state the shared task, assign their specific approach, and list the other agents' approaches so they know to diverge. Each agent must report back with their result when done.
3. Wait for all to report back.


## Swarm Results

### Agent 1 — [Approach Name]
[Result verbatim]

### Agent 2 — [Approach Name]
[Result verbatim]

...

## Diversity Summary
[One sentence per agent on how their approach differed from the others]
