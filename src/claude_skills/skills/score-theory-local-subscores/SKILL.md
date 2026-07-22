---
name: score-theory-local-subscores
description: "Score the given theory according to certain per-theory subscore criteria."
argument-hint: "the theory ID to score (e.g. T_20260414_143100_d4e5f6)"
---

You are the **Theory Scoring Coordinator**. Your task is to assign different subscores to a given theory.

## Input
Arguments: $ARGUMENTS

The arguments contain a single theory ID (like `T_20260414_...`). Parse the theory ID from the arguments.

## Folder setup
All commands must be run in the current working directory. Do not `cd` anywhere else, do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up a context folder for your input:
CONTEXT_DIR: `mktemp -d -p ./tmp score-theory-local-subscores-context-XXXX`

Run this command to populate the context:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context --for_agent_type score-theory-local-subscores --target_folder <CONTEXT_DIR> --from_theory <THEORY_ID>
```

- `<CONTEXT_DIR>/theory/theory.md` — the theory that you're scoring
- `<CONTEXT_DIR>/reviews/<review_id>/review.md` — falsification reviews for this theory. Each one will focus on a different hypothesis from the theory.

## Performing calculations
The execution steps below involve several numeric calculations. Always use `uv run python -c "from math import *; print(<expression>)"` or similar commands to perform calculations, even simple ones. Do not perform calculations manually or in your head.

## Execution Steps
You will invoke a sequence of different skills in order to score the given theory according to different criteria. Do not stop or report results until you have completed ALL of the steps below.

1. **Context Checkout**: Run the bash command above to obtain the theory and review files using `context_manager.py`.
2. **Score Length**: Invoke the `score-length` skill and follow its instructions to obtain a length score for the theory.
3. **Score Guidance Adherence**: Invoke the `score-guidance-adherence` skill and follow its instructions to obtain a guidance adherence score for the theory.
4. **Score Soundness**: Invoke the `score-soundness` skill and follow its instructions to obtain a soundness score for the theory.
5. **Final Output**: Report the theory ID together with each score value (length score, guidance adherence score, and soundness score). Do not include any additional commentary in your output.
