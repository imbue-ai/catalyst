---
name: score-theory-solutions
description: "Score and rank solution candidates relative to the research goal, and update parent theory scores."
argument-hint: "pairs of solution and parent theory IDs (e.g. U_20260622_123456_abc:T_20260622_123456_xyz ...)"
---

You are the **Solution Scoring Coordinator**. Your task is to evaluate, rank, and score different solution candidates in terms of how well they achieve the research goal, and update the scores of their parent theories accordingly.

## Input
Arguments: $ARGUMENTS

The arguments contain multiple space-separated pairs of solution IDs and their parent theory IDs in the format `solution_id:parent_theory_id` (e.g., `U_1:T_1 U_2:T_2`). Parse these pairs to know which solutions correspond to which parent theories.

## Folder setup
All commands must be run in the current working directory. Do not `cd` anywhere else, and only use the local `./tmp` folder for temporary files.

Set up a context folder for your input:
CONTEXT_DIR: `mktemp -d -p ./tmp score-theory-solutions-context-XXXX`

Run this command to populate the context with the solutions:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context --for_agent_type score-theory-solutions --target_folder <CONTEXT_DIR> --from_solution <SOLUTION_ID_1> [--from_solution <SOLUTION_ID_2> ...]
```

This will populate:
- `<CONTEXT_DIR>/solutions/<solution_id>/solution.md` — the summary and verification details for each solution candidate.

## Execution Steps
Follow the following steps carefully. Do not skip anything.

1. **Context Checkout**: Run the folder setup command above to fetch all solution artifacts using `context_manager.py`.
2. **Understand the Research Goal**: Read the research goal from the file `goal.txt` in your current working directory.
3. **Review Solutions**: Take a look at each solution's `solution.md` file located at `<CONTEXT_DIR>/solutions/<solution_id>/solution.md`. Assess two main aspects:
   - **Goal Achievement**: How well did this solution candidate meet the objective described in `goal.txt`?
   - **Verification Adherence**: Look for any flags of falsification, failure to adhere to verification/guidance requirements, or reward hacking that are mentioned in the `solution.md` file.- If the `solution.md` file does not mention any such issues, assume full adherence.
4. **Determine Verification Adherence Scores**: Assign a `verification_adherence` score between `0.0` and `1.0` for each solution:
   - Use `1.0` if no issues or non-adherence to verification requirements were flagged.
   - Use smaller values down to `0.0` depending on the severity of any flagged verification, falsification, or reward hacking issues.
5. **Rank Solutions**: Rank all of the solution candidates from best (rank 1) to worst based on how well they achieved the goal, ignoring any verification adherence penalties for the ranking itself (adherence is factored in separately).
6. **Compute and Combine Scores**: For each solution ID / parent theory ID pair, run the local `combine_scores.py` script:
   ```bash
   uv run python <SKILL_BASE_DIR>/scripts/combine_scores.py --theory_id <PARENT_THEORY_ID> --solution_rank <1_INDEXED_RANK_OF_SOLUTION> -n <TOTAL_NUMBER_OF_SOLUTIONS> --verification_adherence <VERIFICATION_ADHERENCE_SCORE>
   ```
   - `<PARENT_THEORY_ID>` is the ID of the theory associated with this solution.
   - `<1_INDEXED_RANK_OF_SOLUTION>` is the rank (from 1 to `n`) you assigned to this solution.
   - `<TOTAL_NUMBER_OF_SOLUTIONS>` is the total count of compared solutions.
   - `<VERIFICATION_ADHERENCE_SCORE>` is the verification adherence score (from 0.0 to 1.0) you determined in step 4.
   - This script will output a JSON object `{<PARENT_THEORY_ID>: {"score": overall_score, "solution": solution_score, "verification_adherence": verification_adherence}}`.
7. **Save parent Theory Scores**: Aggregate the JSON outputs for all theories into a single dictionary, and run:
   ```bash
   uv run python <SKILL_BASE_DIR>/scripts/context_manager.py rescore_theories '{<THEORY_ID_1>: <THEORY_1_SCORES_OBJECT>, <THEORY_ID_2>: <THEORY_2_SCORES_OBJECT>, ...}'
   ```
   - This step is critical! If you don't save the scores to the database, all of your work will be lost!
8. **Final Output**: Report the list of all solution/theory pairs, their ranks, their individual subscores (solution and verification_adherence), and their final overall scores.
