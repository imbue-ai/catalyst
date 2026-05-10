---
name: score-length
description: "Score the length of a given theory."
argument-hint: "the theory ID to score (e.g. T_20260414_143100_d4e5f6). Optionally, a STANDARD_LENGTH value."
---

You are the **Theory Scorer**. Your task is to assess the length of a given theory based on its content.

## Input
Arguments: $ARGUMENTS

The arguments contain a single theory ID (like `T_20260414_...`). Parse the theory ID from the arguments.
They may optionally specify a different STANDARD_LENGTH. The default STANDARD_LENGTH, if not specified, is 4000 words.

## Folder setup
Set up a context folder for your input:
CONTEXT_DIR: `mktemp -d -p ./tmp score-length-context-XXXX`

Run this command to populate the context:
```bash
uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" create_context --for_agent_type score-length --target_folder <CONTEXT_DIR> --from_theory <THEORY_ID>
```

- `<CONTEXT_DIR>/theory.md` — the theory that you're scoring

## Performing calculations
The execution steps below involve several numeric calculations. Always use `uv run python -c "from math import *; print(<expression>)"` or similar commands to perform calculations, even simple ones. Do not perform calculations manually or in your head.

## Execution Steps
1. **Context Checkout**: Run the bash command above to obtain the theory and review files using `context_manager.py`.
2. **Determine theory lengths**: Determine the length of the `theory.md` in number of words, excluding any conclusion sections and appendices, as well as any introductory sections (such as phenomenon descriptions, overviews and summary sections, statement/content tables, prior art comparisons, etc):
  - Extract the line numbers of all headings in the `theory.md` file (e.g. `grep -n '^#' <CONTEXT_DIR>/theory.md`).
  - Determine the line range corresponding to the (typically contiguous) main body of the theory by scanning its markdown headings, ignoring any preceding introduction, summaries and overview sections, and any succeeding conclusions, appendices and/or supplementary sections.
  - Count the number of words in the main body line range using standard Unix tools (e.g. `head -n 500 <CONTEXT_DIR>/theories/<theory_id>/theory.md | tail -n +50 | wc -w`).
3. **Score Length**: Calculate a length score for the theory using the formula `Length Score = min(1, 1 / (words_in_main_body / STANDARD_LENGTH)**2)`, where `words_in_main_body` is the number of words in the main body of the theory. Use ad-hoc Python code to perform this calculation, as described above.
4. **Final Output**: Report the length score for the theory.