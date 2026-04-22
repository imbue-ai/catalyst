---
name: refine-hypothesis
description: "Attempt to refine a given hypothesis"
allowed-tools: Bash(uv run:*) Bash(mktemp:*) Bash(ls:*) Bash(mkdir -p tmp/*) Bash(cp:*) Read(*) Write(tmp/*) Edit(tmp/*) Skill
argument-hint: "theory ID, review ID(s), and optional literature ID(s) (e.g. T_20260414_143100_d4e5f6 R_20260414_143200_g7h8i9 L_20260414_151000_j0k1l2)"
---

You are an expert scientific agent. You've previously developed a hypothesis for a specific phenomenon. Someone else has reviewed your hypothesis, and found some flaws or limitations. Your goal is to improve this hypothesis based on their falsification results.

## Mandate
- Focus on exactly the hypothesis (observation, theorem or lemma) targeted by the review provided.
- Be thorough in refining the hypothesis. Make sure you verify that your refinements actually address the concerns raised in the falsification report, and don't introduce any new flaws. Typically, you'll want to iterate on this process a few times, refining the hypothesis, propose and run experiments to test the refinements and/or derive mathematical proofs, and then iterate until you have a robust, well-supported hypothesis.
- If experiments or derivations surface a surprising phenomenon, an unfamiliar mathematical structure, or a claim you're not confident about, invoke the `search-literature` skill to look up prior work before committing to a refinement. See the "Literature grounding" section below.
- If you find that the hypothesis is fundamentally flawed or you're unable to find a way to incrementally improve it, please abort and follow the instructions in the "Discarding a flawed hypothesis" section. This is an acceptable result - some hypotheses are just wrong and should be discarded!
- All experiment execution must go through the `run-experiment` skill. Never run a Python experiment script directly. See the "Running experiments" section below.

## Discarding a flawed hypothesis
IF you determine that the hypothesis is fundamentally flawed and cannot be reasonably refined, you should remove it from the theory, along with any other hypotheses or sections that were dependent on it, either directly or indirectly:
1. Carefully review the theory and identify all corollaries, lemmas, theorems, or other sections that either mention the flawed hypothesis, or were clearly relying on it.
2. Repeat this process recursively until you've identified all hypotheses and sections that are dependent on the flawed hypothesis *either directly or indirectly*.
3. Remove the flawed hypothesis itself from the theory
4. For each dependent hypothesis and section, check if there's a straight-forward edit to that hypothesis/section that you can make to avoid the dependency. Otherwise, remove the dependent hypotheses/section from the theory alltogether. Repeat for each dependent hypothesis/section until you've either removed or edited all of them.

## Input
Arguments: $ARGUMENTS

The arguments contain a theory ID (like `T_20260414_...`), one or more review IDs (like `R_20260414_...`), and optionally one or more literature review IDs (like `L_20260414_...`). Parse all IDs from the arguments.

## Folder setup
Set up two folders — one for input context, one for your own output:
CONTEXT_DIR: `mktemp -d -p ./tmp refine-hypothesis-context-XXXX`
OUTPUT_DIR: `mktemp -d -p ./tmp refine-hypothesis-output-XXXX`

Run this command to populate the context, and then initialize the output folder with the original theory files:
```bash
uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" create_context \
    --for_agent_type refine-hypothesis \
    --target_folder <CONTEXT_DIR> \
    --from_theory <THEORY_ID> \
    --from_review <REVIEW_ID_1> [--from_review <REVIEW_ID_2> ...] \
    [--from_literature <LITERATURE_ID_1> --from_literature <LITERATURE_ID_2> ...]
cp -r "<CONTEXT_DIR>/theory/"* "<OUTPUT_DIR>/"
```

- `<CONTEXT_DIR>/theory/` — the original theory (read-only input). Read `<CONTEXT_DIR>/theory/theory.md` and any artifacts.
- `<CONTEXT_DIR>/reviews/<review_id>/` — each falsification report (read-only input). Read each `review.md`.
- `<CONTEXT_DIR>/literature/<literature_id>/` — (if any literature IDs provided, or added mid-run) each literature review, with `summary.md` and downloaded PDFs in `papers/`. Read each `summary.md` and consult individual PDFs when relevant.
- `<OUTPUT_DIR>/` — write your refined theory, experiments, and any supporting notes here.

Any temporary files (including experiment scripts, intermediate results, etc.) must be stored only under `<OUTPUT_DIR>`.

## Running experiments
Every experiment, test, and validation must be set up and run through the `run-experiment` skill, using the AGENT_TYPE `refine-hypothesis`.
Cite each experiment by its `X_ID` in your refined `theory.md` so reviewers can audit the evidence.

## Literature grounding

You may start with zero, one, or many literature reviews already in `<CONTEXT_DIR>/literature/`. During execution, if experiments or derivations raise questions the existing literature (or lack thereof) doesn't answer, invoke the `search-literature` skill with a concise description of the finding/question. It will return a new literature ID (`L_...`). Fold it into your context without rebuilding the folder:

```bash
uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" fetch_literature \
    --target_folder <CONTEXT_DIR> \
    --from_literature <NEW_L_ID>
```

Then read `<CONTEXT_DIR>/literature/<NEW_L_ID>/summary.md` and incorporate its findings into your refinement. You may do this multiple times during a single run if distinct questions arise.

## Execution Steps
1. **Context Checkout**: Run the bash command above to obtain the existing theory, the falsification reports, and literature review results using `context_manager.py`.
2. **Context Review**: Read `<CONTEXT_DIR>/theory/theory.md`, all review files in `<CONTEXT_DIR>/reviews/*/review.md`, and (if present) each `<CONTEXT_DIR>/literature/*/summary.md` to understand the hypothesis, its identified flaws, and any prior literature grounding.
3. **Refinement Idea Generation**: Analyze the falsification reports. Generate ideas for how to address the raised flaws in the current hypothesis. Generate at least 2-3 alternative solutions, such as: more rigid prerequisites or assumptions, localized fixes and modifications to the existing hypothesis, or even a full replacement of the hypothesis by an alternative explanation. Think about how each alternative could be tested and what evidence would support or refute it. Exception: If the reviews didn't raise any flaws, you can stop here and just report back the original theory ID from your inputs.
4. **Validation**: Test your ideas using the available tools.
   - **Experiment**: Invoke `run-experiment`. Reference each experiment's `X_ID` in your notes and refined theory.
   - **Proof**: If applicable, use mathematical derivations.
   - **Literature grounding**: You can cite prior literature to support the hypothesis. Always read the full paper before citing it. In general, if something surprising surfaces, invoke `search-literature` per the "Literature grounding" section to check whether prior literature is available to explain your observation.
5. **Iteration**: Keep iterating until you're COMPLETELY CONFIDENT in your revised hypothesis, or conclude that the hypothesis is fundamentally flawed and should be discarded.
   - Based on the results of the validation step, refine your ideas, generate new ones if necessary, and repeat the validation process.
6. **Reporting**: Write the final revised theory to `<OUTPUT_DIR>/theory.md` (this exact filename is required). Add helpful illustrations and plots from your experiments, or generate additional ones by running appropriate Python scripts. Consider the "Theory Output Format" instructions when writing your final theory.
7. **Store results** Persist your output and return the new theory ID:
   ```bash
   uv run python "${CLAUDE_SKILL_DIR}/scripts/context_manager.py" store_results --from_agent_type refine-hypothesis --from_folder <OUTPUT_DIR> --parent_theory <THEORY_ID>
   ```
   Note down the returned theory ID (e.g. `T_20260414_150000_x1y2z3`) as the result of this skill, together with a brief note on whether you've made significant changes or only very minor refinements to the original theory.

## Theory Output Format
Your `theory.md` file must be: A revised theory that contains your refined hypothesis (or removes the hypothesis if refinement failed).

The revised theory must be a fully self-contained, updated version of the original theory. Do NOT add any notes inside the file about the falsification report or the refinement process. The file should read like a standalone document that presents the final refined hypothesis and any supporting evidence or arguments for it.

Stylistic guidelines for the `theory.md` file:
- Structure your theory into a set of precise definitions, observations, lemmas and/or theorems (collectively referred to as "statements" in the following). Only call something a lemma or theorem if you can formally proof it! Statements that are only based on experimental observation should be labeled as observations. Later lemmas/theorems can build on earlier ones.
- Provide intuition for the mechanisms behind each statement. Then follow up with rigorous mathematical definitions, proofs, and experimental evidence.
- Explicitly state ANY assumptions or limitations that you're making for each statement and list them out clearly.
- Explicitly lay out the evidence you have for each statement, either a mathematical proof/derivation, or empirical evidence from experiments. Perform thorough mathematical derivations and proofs when possible. You can also cite prior literature to support your statements.
- Include plots, figures and specific data points from your experiments to provide intuition and illustrate the evidence for your statements. Make sure to include detailed captions for each plot to explain what is being shown.
- Image references in the markdown file need to be relative to `<OUTPUT_DIR>`. If you want to include images from the exploration context, copy them to your `<OUTPUT_DIR>/` first.
- Cite literature where applicable

As a general guideline, write your theory in a way that resembles a well-written main part of a scientific paper or textbook chapter.