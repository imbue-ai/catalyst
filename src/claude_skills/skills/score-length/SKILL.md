---
name: score-length
description: "Score the length of a given theory."
argument-hint: "the theory ID to score (e.g. T_20260414_143100_d4e5f6). Optionally, a STANDARD_LENGTH value."
user-invocable: false
---

Your task is to assess the length of a given theory based on its content.

Besides the theory to score, you may optionally be given a STANDARD_LENGTH value. The default STANDARD_LENGTH, if not specified, is 7000 words.

## Length Score Execution Steps
1. **Determine theory lengths**: Determine the length of the `theory.md` in number of words, excluding any conclusion sections and appendices, as well as any introductory sections (such as phenomenon descriptions, overviews and summary sections, statement/content tables, prior art comparisons, etc):
  - Extract the line numbers of all headings in the `theory.md` file (e.g. `grep -n '^#' <CONTEXT_DIR>/theory/theory.md`).
  - Determine the line range corresponding to the (typically contiguous) main body of the theory by scanning its markdown headings, ignoring any preceding introduction, summaries and overview sections, and any succeeding conclusions, appendices and/or supplementary sections.
  - Count the number of words in the main body line range using standard Unix tools (e.g. `head -n 500 <CONTEXT_DIR>/theory/theory.md | tail -n +50 | wc -w`).
2. **Score Length**: Calculate a length score for the theory using the formula `Length Score = 1 / (1 + (words_in_main_body / STANDARD_LENGTH)**3)`, where `words_in_main_body` is the number of words in the main body of the theory. Use ad-hoc Python code to perform this calculation, as described above.