---
name: score-theories
description: "Score the quality of a set of theories relative to each other."
argument-hint: "the theory IDs to score (e.g. T_20260414_143100_d4e5f6 T_20260414_143200_g7h8i9)"
---

You are the **Theory Scorer**. Your task is to compare the quality of different theories that all attempt to explain the same phenomenon.

## Input
Arguments: $ARGUMENTS

The arguments contain multiple theory IDs (like `T_20260414_...`). Parse the theory IDs from the arguments.

## Folder setup
Set up a context folder for your input:
CONTEXT_DIR: `mktemp -d -p ./tmp score-theories-context-XXXX`

Run this command to populate the context:
```bash
uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" create_context --for_agent_type score-theories --target_folder <CONTEXT_DIR> --from_theory <THEORY_ID_1> [--from_theory <THEORY_ID_2> ...]
```

- `<CONTEXT_DIR>/theories/<theory_id>/theory.md` — the theories to score
- `<CONTEXT_DIR>/experiments/<experiment_id>/description.md` — descriptions for select experiments that are relevant for scoring these theories

## Performing calculations
The execution steps below involve several numeric calculations. Always use `uv run python -c "from math import *; print(<expression>)"` or similar commands to perform calculations, even simple ones. Do not perform calculations manually or in your head.

## Converting Ranks to Scores
We will use the following methods for converting from a rank `r` (1...n) to a score:
- **Linear score**: `s = (n-r+1)/(n)`
- **Normalized reciprocal score**: `s = (n-r+1) / (r*n)`

## Execution Steps
1. **Folder setup**: Run the bash command above to obtain the theories and experiment files using `context_manager.py`.
2. **Understand the Phenomenon**: Read the first sections of one of the theory files to understand the phenomenon that these theories are trying to explain. You can pick any of the theories for this step, as they should all be trying to explain the same phenomenon.
3. **Rank the Experiments**: Read the `description.md` files for each experiment in `<CONTEXT_DIR>/experiments/` and rank them based on their importance for evaluating the theories. Experiments that validate key qualitative aspects of the phenomenon should rank before those that test peripheral aspects or minor details.
4. **Select Top Experiments**: Select the 10 highest-ranking experiment IDs. Only these will be used in the following steps.
5. **Calculate Experiment Importance Scores**: For each of the selected experiments, calculate an experiment importance score using the *linear score* method.
6. **Generate Theory Predictions**: For each of the theory IDs:
  - Spawn a subagent instructed to invoke the `predict-experiments` skill, passing to it the specific theory ID and the list of selected experiment IDs. This subagent will return a prediction ID (e.g. `P_20260414_143052_a1b2c3`). All subagents can run in parallel.
7. **Collection**: Wait for each subagent to finish and collect their prediction IDs.
8. **Rank Predictions**: For each of the selected experiment IDs: 
  - Spawn a subagent instructed to invoke the `rank-predictions` skill, passing to it the list of prediction IDs the previous step and the experiment ID. This subagent will return a ranked list of theory IDs for that experiment. It might report some theory IDs as NO_PREDICTION if those theories do not make predictions for that experiment. All subagents can run in parallel.
9. **Score Soundness**: For each of the theory IDs:
  - Spawn a subagent instructed to invoke the `score-soundness` skill, passing to it the specific theory ID. The subagent will return a soundness score between 0 and 1 for that theory. All subagents can run in parallel.
10. **Rank Predictive Power**: Spawn a single subagent instructed to invoke the `rank-predictive-power` skill, passing to it the list of theory IDs. 
11. **Collection**: Wait for all subagents from steps 8, 9, and 10 to finish and collect their results.
12. **Score Prediction Rankings**: For each theory, calculate two scores:
  - **Prediction Accuracy Score**: Count the number of experiments for which the theory made a prediction - this will constitute our `n`. Then, turn the rank that the theory received in each experiment into a score, using the *normalized reciprocal score* method. Then, sum these score values, each weighted by the importance score of the corresponding experiment. Finally, normalize the prediction score by dividing it by the sum of importance scores of the experiments for which the theory made a prediction.
  - **Prediction Coverage Score**: Sum the importance scores of the experiments for which the theory made a prediction (regardless of its rank), and divide it by the summed total importance score of all selected experiments.
13. **Score Predictive Power**: Convert the rank of each theory returned by the `rank-predictive-power` skill into a score using the *normalized reciprocal score* method.
14. **Determine theory lengths**: For each theory, determine the length of its `theory.md` in number of words, excluding any appendices, supplementary materials, and introductions:
  - Determine the line range corresponding to the main body of the theory by scanning its markdown headings.
  - Count the number of words in that line range using standard Unix tools (e.g. `head -n 500 <CONTEXT_DIR>/theories/<theory_id>/theory.md | tail -n +50 | wc -w`).
15. **Score Length**: Calculate a length score for each theory using the formula `Length Score = min(1, 1 / (words_in_main_body / 3000)**2)`, where `words_in_main_body` is the number of words in the main body of the theory.
16. **Overall Theory Score**: Combine the scores for each theory into a final score using the formula: `Overall Score = (0.7 * Prediction Accuracy Score + 0.3 * Soundness Score) * (0.4 + (0.3 * Predictive Power Score + 0.3 * Prediction Coverage Score) * Length Score)`.
17. **Save Scores**: Save the overall scores and the detailed subscores to a database, using this bash command:
  ```bash
  uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" rescore_theories '{<THEORY_ID_1>: {"score": <OVERALL_SCORE_1>, "prediction_accuracy": <PREDICTION_ACCURACY_1>, "prediction_coverage": <PREDICTION_COVERAGE_1>, "soundness": <SOUNDNESS_1>, "predictive_power": <PREDICTIVE_POWER_1>, "length": <LENGTH_1>}, <THEORY_ID_2>: {"score": <OVERALL_SCORE_2>, "prediction_accuracy": <PREDICTION_ACCURACY_2>, "prediction_coverage": <PREDICTION_COVERAGE_2>, "soundness": <SOUNDNESS_2>, "predictive_power": <PREDICTIVE_POWER_2>, "length": <LENGTH_2>}, ...}'
  ```
18. **Final Output**: Report the list of all theory IDs along with their final scores, sorted from highest to lowest score. Also include a breakdown of the prediction accuracy, prediction coverage, soundness, predictive power, and length scores for each theory.
