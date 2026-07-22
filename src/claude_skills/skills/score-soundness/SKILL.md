---
name: score-soundness
description: "Score the mathematical soundness of a given theory based on its existing falsification reports."
argument-hint: "the theory ID to score (e.g. T_20260414_143100_d4e5f6)"
user-invocable: false
---

This skill explains how to assess and score the mathematical soundness of a given theory based on its existing falsification reports.

## Soundness Score Execution Steps
1. **Understand the Theory**: If you haven't yet, carefully read the `theory.md` file to understand the theory that you are scoring.
2. **Review Falsification Reports**: Read the `review.md` files for each falsification review.
  - IGNORE any *experimental* or *empirical* falsifications! Instead, focus ONLY on *mathematical* falsifications that point out logical inconsistencies or mathematical errors. If a statement is falsified only experimentally, then treat it as valid for the purpose of this scoring exercise.
  - Each `review.md` file will contain a section `## Target Hypothesis` that describes which statement within the theory is being evaluated, and a `## Conclusion` section which summarizes whether or not the statement was indeed falsified. Read these sections first to understand whether any falsifications were found. You should then read the rest of the review as needed, in order to understand whether the falsification was mathematical or empirical in nature (and disregard it if it is only empirical or experimental).
3. **Score Soundness**: Calculate a soundness score between 0 and 1 for the theory based on the falsification reviews. 1 = zero *mathematical* issues were raised in the reviews, 0.75 = some smaller *mathematical* issues were raised in the reviews, but they are not central to the core theory, 0.5 = a severe *mathematical* flaw was raised in a review which falsifies a key claim of the theory, 0 = several severe *mathematical* flaws were raised throughout multiple reviews, invalidating practically all of the theory. Use your judgment to assign intermediate scores in other scenarios.