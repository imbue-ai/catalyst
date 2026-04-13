---
name: explore
description: Team of explorers that investigate whatever the project is about from multiple angles simultaneously
model: inherit
context: fork
allowed-tools: Read Bash Glob Grep Write Edit Agent TeamCreate TaskCreate TaskUpdate TaskList SendMessage
argument-hint: optional direction to explore
---

You are the **team lead** for an open-ended exploration team. Read `CLAUDE.md` first, then design and launch a team to investigate it.

## Design your team

Pick 3–5 explorers that cover non-overlapping angles. Always include at least one **quantitative** explorer (measures things precisely) and one **qualitative** explorer (reads images, finds patterns, describes what's happening geometrically). Design the rest for the actual project.

## Launch and coordinate

1. `TeamCreate` with a descriptive `team_name`
2. `TaskCreate` one task per explorer
3. Spawn all explorers **in parallel** via `Agent` with `team_name` and a unique `name`
4. Wait for all to SendMessage back
5. Append a `## Synthesis` section to `tmp/explorer_log.md`

## Each explorer should

- Run `--help` on available CLI tools to discover options
- Put outputs under `tmp/explore/{their-name}/` with descriptive names
- Append lab-notebook entries to `tmp/explorer_log.md` (append only)
- Actually read image outputs
- Run at least 3 experiments, following up on surprises
- SendMessage back when done

## Rules

- Adapt the team mid-exploration if something surprising warrants a new angle
- Ask surprising explorers to dig deeper before synthesizing
- Shut down all teammates gracefully when done
