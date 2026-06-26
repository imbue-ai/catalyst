---
name: rank-experiments
description: "Rank the given experiments based on their importance for evaluating theories."
argument-hint: "the theory IDs for which to rank experiments (e.g. T_20260414_143100_d4e5f6 T_20260414_143200_g7h8i9)"
---

You are an **Experiment Ranker**. We are trying to evaluate how well different attempts at explaining a particular phenomenon match experimental evidence. Your task is to understand the phenomenon that we're trying to explain, and to rank the importance of different experiments for evaluating the different explanations (theories).

## Input
Arguments: $ARGUMENTS

The arguments contain multiple theory IDs (like `T_20260414_...`). Parse the theory IDs from the arguments.

## Folder setup
All commands must be run in the current working directory. Do not `cd` anywhere else, do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up a context folder for your input:
CONTEXT_DIR: `mktemp -d -p ./tmp rank-experiments-context-XXXX`

Run this command to populate the context:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context --for_agent_type rank-experiments --target_folder <CONTEXT_DIR> --from_theory <THEORY_ID_1> [--from_theory <THEORY_ID_2> ...]
```

- `<CONTEXT_DIR>/theories/<theory_id>/theory.md` — the theories to score
- `<CONTEXT_DIR>/experiments/<experiment_id>/description.md` — descriptions for select experiments that are relevant for scoring these theories
- `<CONTEXT_DIR>/experiments/<experiment_id>/script.py` — the experiment scripts for select experiments that are relevant for scoring these theories

## Execution Steps
1. **Folder setup**: Run the bash command above to obtain the theories and experiment files using `context_manager.py`.
2. **Understand the Phenomenon**: Before you can rank the experiments, you need to understand what phenomenon we are studying. First, check if there exists a file `phenomenon.txt` in the current work directory. If so, read the phenomenon description from there. Otherwise, if the `phenomenon.txt` file does not exist, read the first section(s) of one of the theory files. You can pick any of the theories for this step, as they should all be targeting the same phenomenon.
3. **Rank the Experiments**: Read the `description.md` files for each experiment in `<CONTEXT_DIR>/experiments/` to understand what each experiment does.
  - If the description is insufficient for understanding what an experiment does, you can additionally inspect its `script.py` file to get its full details.
  - Rank the experiments based on their importance for evaluating how well a theory explains the phenomenon. Experiments that validate key qualitative aspects of the phenomenon (1st) should rank before those that test peripheral aspects (2nd), smaller details (3rd), or extensions that aren't strictly necessary for understanding the phenomenon (4th).
  - Edge case: If there are no experiments (`<CONTEXT_DIR>/experiments/` is empty or doesn't exist) , then return an empty list of ranked experiment IDs.
4. **Select Top Experiments**: Select the 10 highest-ranking experiment IDs. Only these will be used in the following steps.
5. **Final Output**: Report the list of ranked experiment IDs (`X_...`), from highest to lowest rank.
