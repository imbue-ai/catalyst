---
name: rank-explanatory-power
description: "Rank different theories based on their explanatory power"
argument-hint: "the theory IDs to score (e.g. T_20260414_143100_d4e5f6, T_20260414_143200_g7h8i9)"
---

You are the **Theory Ranker**. Your task is to rank different theories in terms of how well they explain a particular target phenomenon. You will be estimating their explanatory power by comparing them to each other.

All theories are attempting to explain the same phenomenon. However, some of them might provide a more thorough and/or generalizable explanation, while others might only explain certain aspects.

Important: Your goal is NOT to assess the correctness or soundness of the theories. Just focus on their explanatory power, assuming they are all correct.

## Input
Arguments: $ARGUMENTS

The arguments contain multiple theory IDs (like `T_20260414_...`). Parse the theory IDs from the arguments.

## Folder setup
All commands must be run in the current working directory. Do not `cd` anywhere else, do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up a context folder for your input:
CONTEXT_DIR: `mktemp -d -p ./tmp rank-explanatory-power-context-XXXX`

Run this command to populate the context:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context --for_agent_type rank-explanatory-power --target_folder <CONTEXT_DIR> --from_theory <THEORY_ID_1> [--from_theory <THEORY_ID_2> ...]
```

- `<CONTEXT_DIR>/theories/<theory_id>/theory.md` — the different theories that you're comparing

## Execution Steps
1. **Context Checkout**: Run the bash command above to obtain the theories and review files using `context_manager.py`.
2. **Understand the Target Phenomenon**: Before you can rank the theories, you need to understand what phenomenon we are studying. First, check if there exists a file `phenomenon.txt` in the current work directory. If so, read the phenomenon description from there. Otherwise, if the `phenomenon.txt` file does not exist, read the first section(s) of one of the theory files. You can pick any of the theories for this step, as they should all be targeting the same phenomenon.
3. **Review Theories**: Take a look at each `theory.md` one by one. Determine how complete its explanation of the target phenomenon is. Make sure you check for complete, detailed explanations. A good explanation illuminates the precise mechanism as to *why* the phenomenon occurs. Hand-wavy explanations, or those that are only at a high level should be discounted. Explanations that can make concrete quantitative predictions are especially good! Also consider how general each theory is. Is its explanation limited to only a narrow domain or value range? More general explanations that can be transferred beyond a specific instance are preferable.
4. **Rank Theories**: Rank the different theories based on their overall explanatory power of the phenomenon (primarily) and their generality (secondarily), assigning rank 1 to the best theory, and so on.
5. **Score Explanatory Power**: Convert the rank of each theory into an associated explanatory power score. To obtain the rank-to-score conversion table, run this command:
  ```bash
  uv run python <SKILL_BASE_DIR>/scripts/ranks_to_scores.py --score_type linear -n <NUMBER_OF_THEORIES>
  ```
  - <NUMBER_OF_THEORIES> is the total number of theories being ranked (i.e. the length of the input theory ID list).
  - The script will output a conversion table, with the rank in column 1, and the corresponding score in column 2.
6. **Final Output**: Report the list of theory IDs together with their respective ranks, from best (rank 1) to worst, and their associated explanatory power scores. Do not include any additional commentary in your output.