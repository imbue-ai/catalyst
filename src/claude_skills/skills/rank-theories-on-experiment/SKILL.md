---
name: rank-theories-on-experiment
description: "Rank different theories based on how well they predict the results of a specific experiment"
allowed-tools: Bash(uv run:*) Bash(mktemp:*) Bash(ls:*) Bash(mkdir -p tmp/*) Bash(cp:*) Read(*) Write(tmp/*) Edit(tmp/*) Agent TeamCreate TaskCreate TaskUpdate TaskList SendMessage
argument-hint: "the theory IDs to rank (e.g. T_20260414_143100_d4e5f6 T_20260414_143200_g7h8i9) and a detailed description of the experiment (how to reproduce it and where to find its raw results)"
---

You are the **Theory Ranker**. Your task is to compare the quality of different theories based on how well they predict the results of a specific experiment.

## Input
Arguments: $ARGUMENTS

The arguments contain multiple theory IDs (like `T_20260414_...`) and a detailed description of the experiment (how to reproduce it and where to find its raw results). Parse the theory IDs and experiment details from the arguments.

## Folder setup

Set up a context folder for your input, passing all theory IDs from the input arguments:
```bash
CONTEXT_DIR=$(mktemp -d -p ./tmp rank-theories-on-experiment-context-XXXX)
uv run python scripts/context_manager.py create_context --for_agent_type rank-theories-on-experiment --target_folder "$CONTEXT_DIR" --from_theory <THEORY_ID_1> [--from_theory <THEORY_ID_2> ...]
```

- `$CONTEXT_DIR/<theory_id>/theory.md` — the theories to rank
- `$CONTEXT_DIR/<theory_id>/reviews/<review_id>/` — a folder containing experiment scripts and other files related to a particular review of the theory, including experiment outputs

DO NOT READ ANY EXPERIMENT RESULTS UNTIL PROMPTED TO DO SO IN THE EXECUTION STEPS BELOW.

## Performing calculations
The execution steps below involve several numeric calculations. Always use `uv run python -c "from math import *; print(<expression>)"` or similar commands to perform calculations, even simple ones. Do not perform calculations manually or in your head.

## Execution Steps
1. **Context Checkout**: Run the bash command above to obtain the theory files and their reviews using `context_manager.py`.
2. **Review the Experiment Details**: Carefully read the detailed description of the experiment provided in the input arguments. Look up the experiment script. Make sure you understand what exactly the experiment does and what its parameters are.
2. **Generate Predictions**: For each theory, read its `theory.md` file. Based on the content of the theory, generate a prediction for the outcome of the experiment. This prediction should be as specific as possible, ideally including approximate numeric predictions for key variables measured in the experiment. If a theory does not make any specific prediction for this experiment, note that down.
3. **Compare Predictions to Results**: Now, read the raw results of the actual experiment (including plots and/or numeric results). If you cannot find the results, feel free to re-run the experiment to obtain them (store any temporary result files into `$CONTEXT_DIR`). Compare each theory's prediction to the actual results.
4. **Rank the Theories**: Rank the theories based on how closely their predictions matched the actual results. The theory whose predictions are closest to the actual results should receive rank 1, the next closest rank 2, and so on. Only include theories that made a prediction for this experiment in the ranking.
10. **Final Output**: Report the ranked list of theory IDs together with their ranks, from best fit (rank 1) to worst fit. Additionally, report a separate list of theory IDs that did not make any prediction for this experiment, under the heading "NO_PREDICTIONS".
