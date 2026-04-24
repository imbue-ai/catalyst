---
name: score-soundness
description: "Score the mathematical soundness of a given theory based on its existing falsification reports."
argument-hint: "the theory ID to score (e.g. T_20260414_143100_d4e5f6)"
---

You are the **Theory Scorer**. Your task is to assess the mathematical soundness of a given theory based on its existing falsification reports.

## Input
Arguments: $ARGUMENTS

The arguments contain a single theory ID (like `T_20260414_...`). Parse the theory ID from the arguments.

## Folder setup
Set up a context folder for your input:
CONTEXT_DIR: `mktemp -d -p ./tmp score-soundness-context-XXXX`

Run this command to populate the context:
```bash
uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" create_context --for_agent_type score-soundness --target_folder <CONTEXT_DIR> --from_theory <THEORY_ID>
```

- `<CONTEXT_DIR>/theory.md` — the theory that you're scoring
- `<CONTEXT_DIR>/reviews/<review_id>/review.md` — falsification reviews for this theory. Each one will focus on a different hypothesis from the theory.

## Execution Steps
1. **Context Checkout**: Run the bash command above to obtain the theory and review files using `context_manager.py`.
2. **Understand the Theory**: Read the `theory.md` file to understand the theory that you are scoring.
3. **Review Falsification Reports**: Read the `review.md` files for each falsification review. Ignore any experimental falsifications! Instead, focus on mathematical falsifications that point out logical inconsistencies, mathematical errors, or flawed assumpsions.
4. **Score Soundness**: Calculate a soundness score between 0 and 1 for the theory based on the falsification reviews. 1 = zero issues were raised in the reviews, 0 = several severe flaws were raised in the reviews. Use your judgment to assign intermediate scores for cases where some issues were raised but they were not severe or there were only a few minor issues.
5. **Final Output**: Report the soundness score for the theory.