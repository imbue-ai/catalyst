---
name: write-different-theory
description: "Write a theory taking a *different* approach from the provided ones."
argument-hint: "A list of prior theory IDs (T_20260414_..., ...), optional literature ID (e.g. L_20260414_...)."
---

You are an expert scientific agent. Your goal is to develop a theory to explain a given phenomenon. Some previous attempts have been made to explain the phenomenon, but they turned out to be unsatisfactory. So your goal is to AVOID taking the same approaches as the previous theories, and instead come up with a *different* explanation that accounts for the phenomenon and is supported by evidence.

## Previous theory input
Arguments: $ARGUMENTS

The arguments contain a list of prior theory IDs (like `T_20260414_...`), and an optional literature review ID (like `L_20260414_...`). Parse all IDs from the arguments.

## Previous theory folder setup
All commands must be run in the current working directory. Do not `cd` anywhere else.

Set up a folder to hold the pre-existing theories:
CONTEXT_DIR: `mktemp -d -p ./tmp write-different-theory-context-XXXX`

Run this command to populate the context:
```bash
uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" create_context --for_agent_type write-different-theory --target_folder <CONTEXT_DIR> --from_theory <THEORY_ID_1> [--from_theory <THEORY_ID_2> ...]
```

- `<CONTEXT_DIR>/theories/<theory_id>/theory.md` — the previous theory attempts that we're trying to be different from.

## Outer Execution Steps
1. **Context Checkout**: Run the bash command above to obtain the previous theories using `context_manager.py`.
2. **Understand the Phenomenon**: Before you can start working on a new theory, you need to understand what phenomenon we are studying. First, check if there exists a file `phenomenon.txt` in the current work directory. If so, read the phenomenon description from there. Otherwise, if the `phenomenon.txt` file does not exist, read the first section(s) of one of the theory files. You can pick any of the theories for this step, as they should all be targeting the same phenomenon.
3. **Understand Previous Theories**: Read the previous theories in `<CONTEXT_DIR>/theories/<theory_id>/theory.md`. Understand the approaches they took, identify the assumptions they made, the angles they explored, and the evidence they used. This will help you figure out how to take a different approach.
4. **Write a Different Theory**: Invoke the `write-theory` skill, passing to it the phenomenon description, and the literature review ID if available. Follow all instructions and execution steps provided in that skill, BUT make sure that the new theory takes a FUNDAMENTALLY DIFFERENT approach from all of the previous theories. You might have to iterate and explore for a while to find a different angle, so please take your time and be creative. It is expected that you have to run through multiple cycles of hypothesis development and experimentation before you arrive at a properly novel perspective. When the write-theory skill is done, it will provide a new theory ID (e.g. `T_20260414_143100_d4e5f6`) that forms the result of this skill.