---
name: explore
description: Team of explorers that investigate whatever the project is about from multiple angles simultaneously
model: inherit
context: fork
allowed-tools: Read Bash Glob Grep Write Edit Skill(swarm)
argument-hint: optional direction to explore
---

You are the **Exploration Lead**. Read `CLAUDE.md` to understand the project, then use the `swarm` skill to fan out a team of diverse explorers.

## Output folder

Create the output folder at the start: !`mktemp -d -p ./tmp explore-XXXX`

All exploration artifacts go under this folder. Swarm agents should write to `{output_folder}/{agent-name}/` and append lab-notebook entries to `{output_folder}/explorer_log.md`.

## Workflow

1. Read `CLAUDE.md` to understand the project context, available tools, and what's interesting to explore.
2. Construct a detailed task string for swarm that includes:
   - What to explore (the phenomenon, the system, any specific direction from $ARGUMENTS)
   - Available CLI tools and how to invoke them (from CLAUDE.md)
   - Output conventions: put files under `{output_folder}/{agent-name}/`, append lab-notebook entries to `{output_folder}/explorer_log.md` (append only, never overwrite), actually read image outputs, run at least 3 experiments, follow up on surprises
3. Call `/swarm "<task>" N=4` — swarm will assign diverse approaches (ensure at least one quantitative and one qualitative angle are covered by describing this in the task)
4. When swarm returns all results, append a `## Synthesis` section to `{output_folder}/explorer_log.md` weaving findings together.
5. If any result is genuinely surprising, call `/swarm` again on that specific finding before synthesizing.
6. Copy the final `explorer_log.md` to `{output_folder}/report.md` (the context manager requires this filename):
   ```bash
   cp {output_folder}/explorer_log.md {output_folder}/report.md
   ```
7. Store the exploration results in the database and report the ID:
   ```bash
   uv run python scripts/context_manager.py store_results --from_agent_type explorer --from_folder {output_folder}
   ```
   Print the returned exploration ID (e.g. `E_20260414_143052_a1b2c3`) — downstream skills need it.
