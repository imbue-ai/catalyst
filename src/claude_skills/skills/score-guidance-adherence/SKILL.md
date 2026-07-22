---
name: score-guidance-adherence
description: "Score how well the given theory adheres to the provided guidance."
argument-hint: "the theory ID to score (e.g. T_20260414_143100_d4e5f6)"
user-invocable: false
---

This skill explains how to assess and score how well a given theory adheres to the provided user guidance.

## Guidance Adherence Score Execution Steps
1. **Check Guidance**: User guidance can come from two places: a) the file `phenomenon.txt`, and/or b) the file `GUIDANCE.txt`, both in the current working directory. Zero, one, or both of the files might exist. Check which one(s) exists, and read them to determine whether the user has provided any specific guidance on what kind of theory they're looking for. 
  - Note that `phenomenon.txt` (if it exists), will also contain a description of the phenomenon that is being investigated. Disregard that part, as we are only interested in any *additional* constraints that it imposes on the type of theory that the user is interested in, not on *what* the theory should explain.
  - If neither file exists, or neither contain any prescriptive guidance on what type of theory the user expects, you can skip the next step and just assign a score of 1 (trivially full adherence to guidance, since there is no guidance).
2. **Understand the Theory**: If you haven't yet, carefully read the `theory.md` file to understand the theory that you are scoring.
3. **Score Adherence**: Assign a Guidance Adherence Score between 0 and 1. Check if the theory in `theory.md` adheres to all user-provided guidance from the sources mentioned above. Assign a score of 1 if it strictly adheres to all guidance, 0.5 if it adheres to some but not all guidance or only partially adheres to some key guidance, and 0 if it doesn't adhere to any relevant guidance. Use your judgment to assign intermediate scores in other scenarios.