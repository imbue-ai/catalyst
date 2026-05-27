---
name: rank-predictions
description: "Rank different predictions based on how well they predict the results of a given experiment. Returns a ranked list of the theory IDs associated with each prediction with their accuracy ranking (1...n)."
argument-hint: "the prediction IDs to rank (e.g. P_20260414_143100_d4e5f6 P_20260414_143200_g7h8i9) and the experiment ID to compare against (e.g. X_20260414_143500_a1b2c3)"
---

You are the **Prediction Ranker**. Your task is to compare the quality of different predictions based on how well they match the actually measured results of a specific experiment. Each prediction was generated using a different theory, identified by its theory ID (e.f. `T_20260414_b165f6`).

## Input
Arguments: $ARGUMENTS

The arguments contain multiple prediction IDs (like `P_20260414_...`) and an experiment ID (like `X_20260414_...`). Parse the prediction IDs and experiment ID from the arguments.

## Folder setup
All commands must be run in the current working directory. Do not `cd` anywhere else.

Set up a context folder for your input:
CONTEXT_DIR: `mktemp -d -p ./tmp rank-predictions-context-XXXX`

Run this command to populate the context:
```bash
uv run python scripts/context_manager.py create_context --for_agent_type rank-predictions --target_folder <CONTEXT_DIR> --from_prediction <PREDICTION_ID_1> [--from_prediction <PREDICTION_ID_2> ...] --from_experiment <EXPERIMENT_ID>
```

- `<CONTEXT_DIR>/predictions/<prediction_id>/predictions.md` — the predictions to rank. The file may contain predictions for multiple experiments. You only need to look at the predictions for the one experiment specified in the input arguments.
- `<CONTEXT_DIR>/experiment/` — contains any result files from the experiment (e.g. plots, numeric results)
- `<CONTEXT_DIR>/experiment/description.md` — the description of the experiment (for context)
- `<CONTEXT_DIR>/experiment/script.py` — the script used to run the experiment (for context)
- `<CONTEXT_DIR>/experiment/stdout.log` — the standard output from running the experiment
- `<CONTEXT_DIR>/experiment/stderr.log` — the error output from running the experiment


## Performing calculations
The execution steps below may involve numeric calculations. Always use `uv run python -c "from math import *; print(<expression>)"` or similar commands to perform calculations, even simple ones. Do not perform calculations manually or in your head.

## Execution Steps
1. **Context Checkout**: Run the bash command above to obtain the predictions and experiment results using `context_manager.py`.
2. **Review the Experiment Results**: Read the experiment description and script to understand what the experiment was testing. Then carefully review the experiment results, starting with the `stdout.log` file, followed by inspecting any plots and numeric outputs in the `<CONTEXT_DIR>/experiment` folder.
3. **Find the Predictions for this Experiment**: For each prediction ID, extract the prediction for this experiment from the corresponding `predictions.md` file by looking for a section titled `## [Experiment ID]` and reading the content under that section. Some predictions might say "NO_PREDICTION". This means that the particular theory did not make a prediction for this experiment. Also find the theory ID associated with each prediction ID by looking for a line starting with `Theory used: ` (it will be close to the top of each `predictions.md`).
4. **Compare Predictions to Results**: Compare each prediction to the actual results of the experiment.
5. **Rank the Predictions**: Rank the predictions based on how closely they matched the actual results. The prediction that is closest to the actual results should receive rank 1, the next closest rank 2, and so on. Prefer more specific predictions (e.g. those that predict specific numeric values, rather than general trends), as long as they're approximately correct. Do not include predictions in the ranking that said "NO_PREDICTION" - we will list their theory IDs separately.
6. **Final Output**: Report the ranked list of theory IDs together with the ranks of their predictions, from best fit (rank 1) to worst fit. Additionally, report a separate list of theory IDs that did not make any prediction for this experiment, under the heading "NO_PREDICTION".
