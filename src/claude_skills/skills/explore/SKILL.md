---
name: explore
description: Team of explorers that investigate a scientific phenomenon from multiple angles simultaneously
allowed-tools: Read Bash Glob Grep Write Edit Skill(swarm)
argument-hint: the phenomenon and optionally direction to explore
---

You are the **Exploration Lead**. You will be given a scientific phenomenon to explore, and then use the `swarm` skill to fan out a team of diverse explorers.

## Inputs
The phenomenon to explore is: $ARGUMENTS

## Output folder
Create the output folder at the start:
OUTPUT_DIR: `mktemp -d -p ./tmp explore-output-XXXX`

All exploration artifacts and temporary files go under this folder. Swarm agents should write to `<OUTPUT_DIR>/{agent-name}/` and append lab-notebook entries to `<OUTPUT_DIR>/explorer_log.md`.

## Workflow

1. Understand the given phenomenon and what's interesting to explore around it.
2. Construct a detailed task string for swarm that includes:
   - What to explore (the phenomenon, the system, any specific direction from your inputs)
   - Available CLI tools and how to invoke them (if provided)
   - Output conventions: put files under `<OUTPUT_DIR>/<agent-name>/`, append lab-notebook entries to `<OUTPUT_DIR>/explorer_log.md` (append only, never overwrite), actually read image outputs, run at least 3 experiments, follow up on surprises
   - Experiment discipline: You must not execute experiment scripts directly. Every experiment goes through the `run-experiment` skill, using the AGENT_TYPE `explorer`. Record each resulting `X_...` experiment ID in your lab-notebook entry alongside a one-line summary of the finding.
   - Encourage it to include plots, figures, and visualizations that come from the experiments as part of `explorer_log.md`. Markdown image references should be relative to `<OUTPUT_DIR>/`.
3. Invoke the swarm skill `/swarm "<task>" N=4` — swarm will assign diverse approaches (ensure at least one quantitative and one qualitative angle are covered by describing this in the task)
4. When swarm returns all results, append a `## Synthesis` section to `<OUTPUT_DIR>/explorer_log.md` weaving findings together.
5. If any result is genuinely surprising, call `/swarm` again on that specific finding before synthesizing.
6. Copy the final `explorer_log.md` to `<OUTPUT_DIR>/report.md` (the context manager requires this filename):
   ```bash
   cp <OUTPUT_DIR>/explorer_log.md <OUTPUT_DIR>/report.md
   ```
7. Store the exploration results in the database and return the ID:
   ```bash
   uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" store_results --from_agent_type explorer --from_folder <OUTPUT_DIR>
   ```
   Note down the printed exploration ID (e.g. `E_20260414_143052_a1b2c3`) as the result of this skill.
