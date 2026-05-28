---
name: score-theories
description: "Score the quality of the given theories relative to each other and update all population scores."
argument-hint: "the theory IDs to score (e.g. T_20260414_143100_d4e5f6 T_20260414_143200_g7h8i9)"
---

You are the **Theory Scoring Coordinator**. Your task is to compare the quality of different theories by coordinating different scoring subagents, and then combining their results into overall theory scores.

## Input
Arguments: $ARGUMENTS

The arguments contain multiple theory IDs (like `T_20260414_...`). Parse the theory IDs from the arguments.

## Execution Steps
Follow the following steps carefully. Do not skip anything. Do not take shortcuts.

1. **Obtain Ranked Experiment IDs**: Launch a subagent instructed to invoke the `rank-experiments` skill, passing to it the list of theory IDs. The subagent will return the highest-ranking experiment IDs (`X_...`), from highest rank to lowest rank. These are the experiment IDs that we will be using to evaluate the theories in the following steps. Wait for the subagent to finish and collect its response with the ranked experiment IDs.
2. **Generate Theory Predictions**: For each of the theory IDs individually:
  - Spawn a subagent instructed to invoke the `predict-experiments` skill, passing to it the specific theory ID and the list of ranked experiment IDs. This subagent will return a prediction ID (e.g. `P_20260414_143052_a1b2c3`). All subagents can run in parallel.
3. **Collect Predictions**: Wait for each subagent to finish and collect their final result messages containing the prediction IDs.
4. **Rank Predictions**: For each of the ranked experiment IDs individually:
  - Spawn a subagent instructed to invoke the `rank-predictions` skill, passing to it the list of prediction IDs from the previous step, and a single experiment ID. This subagent will return a ranked list of theory IDs for that one experiment. It might report some theory IDs as NO_PREDICTION if those theories do not make predictions for that experiment. All subagents can run in parallel.
5. **Score Soundness**: For each of the theory IDs:
  - Spawn a subagent instructed to invoke the `score-soundness` skill, passing to it the specific theory ID. The subagent will return a soundness score between 0 and 1 for that theory. All subagents can run in parallel.
6. **Score Length**: For each of the theory IDs:
  - Spawn a subagent instructed to invoke the `score-length` skill, passing to it the specific theory ID. The subagent will return a length score between 0 and 1 for that theory. All subagents can run in parallel.
7. **Score Guidance Adherence**: For each of the theory IDs:
  - Spawn a subagent instructed to invoke the `score-guidance-adherence` skill, passing to it the specific theory ID. The subagent will return a guidance adherence score between 0 and 1 for that theory. All subagents can run in parallel.
8. **Rank Explanatory Power**: Spawn a single subagent instructed to invoke the `rank-explanatory-power` skill, passing to it the list of theory IDs.
9. **Collection**: Wait for all subagents from steps 4, 5, 6, 7, and 8 to finish and collect their final result messages.
10. **Score Prediction Rankings**: For each theory, invoke a script to calculate two scores, the prediction accuracy score and the prediction coverage score:
  ```bash
  uv run python <SKILL_BASE_DIR>/scripts/compute_prediction_scores.py -n <NUMBER_OF_THEORIES> --theory_id <THEORY_ID> --ranks <PREDICTION_RANK_ON_EXPERIMENTS_LIST>
  ```
  - <NUMBER_OF_THEORIES> is the total number of theories being scored (i.e. the length of the input theory ID list).
  - The `<PREDICTION_RANK_ON_EXPERIMENTS_LIST>` is a comma-separated list of the ranks of this theory's predictions for each of the selected experiments, in order of experiment ranking. Include a "NO_PREDICTION" for experiments where the current theory did not make a prediction. For example, if there were 3 selected experiments and this theory ranked 1st for the first experiment, 3rd for the second, and did not make a prediction for the third, then the list would be: `1,3,NO_PREDICTION`.
  - The script will output the prediction accuracy score and the prediction coverage score for this theory.
11. **Score Explanatory Power**: Convert the rank of each theory returned by the `rank-explanatory-power` skill into an associated score. To obtain the rank-to-score conversion table, run this command:
  ```bash
  uv run python <SKILL_BASE_DIR>/scripts/ranks_to_scores.py --score_type linear -n <NUMBER_OF_THEORIES>
  ```
  - <NUMBER_OF_THEORIES> is the total number of theories being scored (i.e. the length of the input theory ID list).
  - The script will output a conversation table, with the rank in column 1, and the corresponding score in column 2.
12. **Overall Theory Score**: Combine the scores for each theory into an overall score object, one for each theory, by running:
  ```bash
  uv run python <SKILL_BASE_DIR>/scripts/combine_scores.py --theory_id <THEORY_ID> --prediction_accuracy <PREDICTION_ACCURACY_SCORE> --prediction_coverage <PREDICTION_COVERAGE_SCORE> --soundness <SOUNDNESS_SCORE> --explanatory_power <EXPLANATORY_POWER_SCORE> --length <LENGTH_SCORE> --adherence <GUIDANCE_ADHERENCE_SCORE>
  ```
  - The script will output a JSON object `{<THEORY_ID>: { ... }}` containing both the overall score, and all subscores for the given theory. You will use this output in the next step.
13. **Save Scores**: Save the overall scores and the detailed subscores to a database, using this bash command:
  ```bash
  uv run python <SKILL_BASE_DIR>/scripts/context_manager.py rescore_theories '{<THEORY_ID_1>: <THEORY_1_SCORES_OBJECT>, <THEORY_ID_2>: <THEORY_2_SCORES_OBJECT>, ...}'
  ```
  - Where <THEORY_X_SCORES_OBJECT> is the JSON object output from the previous step for theory X, containing both the overall score and the subscores for that theory.
  - This step is critical! If you don't save the scores to the database, all of your work will be lost!
14. **Final Output**: Report the list of all theory IDs along with their final scores, sorted from highest to lowest score. Also include a breakdown of the different subscores for each theory.
