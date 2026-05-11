---
name: streamline-theory-variations
description: "Streamline a theory down to its core essence, selecting a few different options."
argument-hint: "theory ID (e.g. T_20260414_143100_d4e5f6)"
---

## Input
Arguments: $ARGUMENTS

The arguments contain a theory ID (like `T_20260414_...`).

## Execution Steps
You will run the `streamline-theory` skill multiple times, each in a separate parallel subagent, and each with a different instruction for which key story to focus on.
In particular:
1. Launch one subagent to run `streamline-theory` with the instruction to focus on "the most novel aspect". Also pass it the input theory ID.
2. Launch one subagent to run `streamline-theory` with the instruction to focus on "the most insightful aspect". Also pass it the input theory ID.
3. Launch one subagent to run `streamline-theory` with the instruction to focus on "the most foundational aspect". Also pass it the input theory ID.
4. Launch one subagent to run `streamline-theory` with the instruction to focus on "the most universally applicable aspect". Also pass it the input theory ID.
5. Launch one subagent to run `streamline-theory` with the instruction to focus on "the most speculative and ambitious aspect". Also pass it the input theory ID.

All subagents can run in parallel. Each one will report back a new theory ID (e.g. `T_20260414_150000_x1y2z3`). Wait for all subagents to finish and collect their final result messages containing the returned theory IDs. Report the list of returned theory IDs as the output of this skill.