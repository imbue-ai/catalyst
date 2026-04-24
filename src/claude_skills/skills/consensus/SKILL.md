---
name: consensus
description: "Swarm a question to N agents and tally their agreement to produce a consensus answer with dissent noted"
argument-hint: The question or task to reach consensus on. Optionally specify N agents (default 5, odd preferred).
---

You are the **Consensus Builder**. Use the `swarm` skill to fan out a question to N independent agents, then tally their conclusions.

## Input
Question/task to reach consensus on (and optionally N): $ARGUMENTS

## Workflow

1. Call `/swarm "<question> — each agent must end their response with a single unambiguous conclusion" N=5` (or specified N, preferring odd numbers to avoid ties)
2. When swarm returns, parse each agent's conclusion from their result
3. Tally: group agents by conclusion, count agreement
4. Output the consensus result (see format below)

## Final Output Format

## Consensus Result

**Question**: [question]
**Verdict**: [majority conclusion] ([N]/[total] agents agree)

## Agent Breakdown

| Agent | Approach | Conclusion |
|-------|----------|------------|
| 1 | [approach] | [conclusion] |
| ... | ... | ... |

## Dissent
[Minority conclusions and their reasoning, if any. Omit section if unanimous.]

## Synthesis
[Final answer informed by the majority, incorporating any important nuance from dissenters.]
