---
name: rank-theories
description: "Rank different theories"
allowed-tools: Bash(uv run:*) Bash(mktemp:*) Bash(ls:*) Bash(mkdir -p tmp/*) Bash(cp:*) Read(*) Write(tmp/*) Edit(tmp/*) Agent TeamCreate TaskCreate TaskUpdate TaskList SendMessage
argument-hint: "the theory IDs to rank (e.g. T_20260414_143100_d4e5f6 T_20260414_143200_g7h8i9)"
---

You are the **Theory Ranker**. Your task is to compare the quality of different theories that all attempt to explain the same phenomenon.

## Input
Arguments: $ARGUMENTS

The arguments contain multiple theory IDs (like `T_20260414_...`). Parse the theory IDs from the arguments.

## Folder setup

Set up a context folder for your input, passing all theory IDs from the input arguments:
```bash
CONTEXT_DIR=$(mktemp -d -p ./tmp rank-theories-context-XXXX)
uv run python scripts/context_manager.py create_context --for_agent_type rank-theories --target_folder "$CONTEXT_DIR" --from_theory <THEORY_ID_1> [--from_theory <THEORY_ID_2> ...]
```

- `$CONTEXT_DIR/<theory_id>/theory.md` — the theory files to rank
- `$CONTEXT_DIR/<theory_id>/reviews/` — a folder containing one or multiple reviews for the theory. Each review is in its own folder:
- `$CONTEXT_DIR/<theory_id>/reviews/<review_id>/review.md` — the review report
- `$CONTEXT_DIR/<theory_id>/reviews/<review_id>/` — a folder containing experiment scripts and other files related to the review, including experiment outputs

## Performing calculations
The execution steps below involve several numeric calculations. Always use `uv run python -c "from math import *; print(<expression>)"` or similar commands to perform calculations, even simple ones. Do not perform calculations manually or in your head.

## Execution Steps
1. **Context Checkout**: Run the bash command above to obtain the theory files and their reviews using `context_manager.py`.
2. **Generate Experiment List**: Read each of the review reports (`review.md`) for each theory and extract the list of experiments that were conducted to evaluate the theory. Create a distinct list of all experiments across all reviews and theories, removing any duplicates.
3. **Rank the Experiments**: Rank the distinct experiments based on their importance for evaluating the theories. Experiments that validate key qualitative aspects of the phenomenon should rank before those that test peripheral aspects or minor details.
4. **Select Top Experiments**: Select the 10 highest-ranking distinct experiments. Only these will be used in the following steps.
5. **Calculate Experiment Importance Scores**: For each of the selected experiments, calculate an importance score using the formula `(n-r)/(n-1)`, where `r` is the position of the experiment in the ranked list (starting from 1), and `n` is the total number of selected experiments.
6. **Rank the Theories on Each Experiment**: For each of the selected experiments:
  - Spawn a subagent instructed to invoke the `rank-theories-on-experiment` skill, passing to it the list of theory IDs and the details needed for reproducing the experiment. Also pass it the file names where it can find the raw results of the experiment (including any plots and numeric outputs). This agent will rank the theories based on how well they predict the given experiment's results. It might also determine that some of the theories do not make any prediction for this experiment, returning the list of those theories as a separate NO_PREDICTIONS list.
7. **Collection**: Wait for each subagent to finish and collect their rankings and NO_PREDICTION lists.
8. **Aggregate Rankings**: For each theory, calculate two scores:
  - **Prediction Score**: First, turn the rank that the theory received in each experiment (for which it made a prediction) into a rank score, using the formula `s = (n-r) / (r*(n-1))`, where `r` is the rank that the theory received in the experiment, and `n` is the total number of selected experiments. Then, sum of these score values, each weighted by the importance score of the corresponding experiment. Finally, normalize the prediction score by dividing it by the sum of importance scores of the experiments for which the theory made a prediction.
  - **Coverage Score**: Sum of the importance scores of the experiments for which the theory made a prediction (regardless of its rank), divided of the total importance score of all selected experiments.
9. **Final Theory Score**: Combine the prediction score and coverage score for each theory into a final score using the formula: `Final Score = Prediction Score * Coverage Score`.
10. **Final Output**: Report the list of all theory IDs along with their final scores, sorted from highest to lowest score. Also include a breakdown of the prediction and coverage scores for each theory.
