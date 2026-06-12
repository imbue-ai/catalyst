---
name: improve-adherence
description: "Improve a theory based on adherence review findings"
argument-hint: "theory ID, review ID(s), and optional literature ID(s) (e.g. T_20260414_143100_d4e5f6 R_20260414_143200_g7h8i9)"
---

You are an expert scientific agent. You have previously developed a theory, and an adherence review has identified constraints that were violated or gaps in your explanation of the phenomenon. Your goal is to improve and refine the theory to fully adhere to all guidance/constraints and completely explain the phenomenon.

## Mandate
- Focus on addressing the specific adherence concerns and explanatory coverage gaps raised in the review(s) provided.
- Be thorough in refining the theory (`theory.md`). Ensure you resolve all violations of `GUIDANCE.txt` or `phenomenon.txt`, and expand the theoretical statements or models to fully cover the target phenomenon.
- Maintain the overall scientific rigor, consistency, and style of the theory.
- All experiment execution must go through the `run-experiment` skill. Never run a Python experiment script directly.

## Input
Arguments: $ARGUMENTS

The arguments contain a theory ID (like `T_20260414_...`), one or more review IDs (like `R_20260414_...`), and optionally one or more literature review IDs (like `L_20260414_...`). Parse all IDs from the arguments.

## Folder setup
All commands must be run in the current working directory. Do not `cd` anywhere else, do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up two folders — one for input context, one for your own output:
CONTEXT_DIR: `mktemp -d -p ./tmp improve-adherence-context-XXXX`
OUTPUT_DIR: `mktemp -d -p ./tmp improve-adherence-output-XXXX`

Run this command to populate the context, and then initialize the output folder with the original theory files:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context \
    --for_agent_type improve-adherence \
    --target_folder <CONTEXT_DIR> \
    --from_theory <THEORY_ID> \
    --from_review <REVIEW_ID_1> [--from_review <REVIEW_ID_2> ...] \
    [--from_literature <LITERATURE_ID_1> ...]
cp -r "<CONTEXT_DIR>/theory/"* "<OUTPUT_DIR>/"
```

- `<CONTEXT_DIR>/theory/` — the original theory (read-only input). Read `<CONTEXT_DIR>/theory/theory.md` and any artifacts.
- `<CONTEXT_DIR>/reviews/<review_id>/` — each adherence review report (read-only input). Read each `review.md`.
- `<CONTEXT_DIR>/literature/<literature_id>/` — (if any literature IDs provided, or added mid-run) each literature review, with `summary.md` and downloaded TeX sources or PDFs in `papers/`. Read the `summary.md` and consult individual papers when relevant.
- `<OUTPUT_DIR>/` — write your updated theory, experiments, and any supporting notes here.

## Obtaining cited experiment IDs
Your inputs may cite specific experiment IDs (`X_...`). You can retrieve these experiments and their results by running:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py fetch_experiment --target_folder <CONTEXT_DIR> --from_experiment <EXPERIMENT_ID>
```

This command will place the experiment description (`description.md`), Python script (`script.py`), and results into the `<CONTEXT_DIR>/experiments/<EXPERIMENT_ID>` folder.

## Running experiments
Every experiment, test, and validation must be set up and run through the `run-experiment` skill, using the AGENT_TYPE `improve-adherence`.
Cite each experiment by its `X_...` ID in your improved `theory.md` so reviewers can audit the evidence.

## Literature grounding
You may start with zero, one, or many literature reviews already in `<CONTEXT_DIR>/literature/`. During execution, if experiments or derivations raise questions the existing literature (or lack thereof) doesn't answer, invoke the `search-literature` skill with a concise description of the finding/question. It will return a new literature ID (`L_...`). Fold it into your context without rebuilding the folder:

```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py fetch_literature \
    --target_folder <CONTEXT_DIR> \
    --from_literature <NEW_L_ID>
```

Then read `<CONTEXT_DIR>/literature/<NEW_L_ID>/summary.md` and incorporate its findings into your theory. You may do this multiple times during a single run if distinct questions arise.

## Theory Output Format
Your `theory.md` file must be: A revised theory that addresses the adherence reviews.

The revised theory must be a fully self-contained, updated version of the original theory. Do NOT add any notes inside the file about the adherence review or the improvement process itself. The file should read like a standalone document that presents the final improved theory.

Please maintain the following guidelines for the improved theory:
- Start with a brief definition of the phenomenon and provide any necessary context, including a brief summary of the relevant literature.
- Then, provide a highly concise "key insights" summary of your theory. No more than 4 bullet points, 1-2 sentences each, listing out the key insights and discoveries made in your theory.
- Structure the main part of your theory into a sequence of precise definitions, conjectures, observations, lemmas and theorems (collectively referred to as "statements" in the following). Only call something a lemma or theorem if you can formally prove it! Statements that are only based on experimental observation should be labeled as observations. Later statements can build on earlier ones.
- Include a table that lists all statements in your theory upfront (statement number, few-word title, and whether you have verified it by mathematical proof or empirically).
- Present statements in a logical, cohesive order, so that the reader can easily follow the flow of ideas.
- Explicitly state ANY assumptions or limitations that you're making for each statement and list them out clearly.
- Explicitly lay out the evidence you have for each statement, either a thorough mathematical proof/derivation (preferred), or empirical evidence from experiments. You can also cite prior literature to support your statements. Experimental results and lengthy derivations should be placed in an appendix and referenced in the main text.
- Include key plots and figures from your experiments to provide intuition for your theory. Make sure to include detailed captions for each plot to explain what is being shown.
- Image references in the markdown file need to be relative to `<OUTPUT_DIR>`. NEVER use absolute paths. Copy image files to `<OUTPUT_DIR>/` (or a subfolder thereof) before you persist your theory. Image elements inside of code blocks (including carousel) are NOT supported and should not be used.
- Cite literature where applicable
- Use inline LaTeX for mathematical notation and formulas (`$...$` for inline math, and `$$...$$` for display math). Do NOT put formulas into code blocks.

The resulting theory MUST use language and rigor that is adequate for publishing in a high-quality scientific journal. Use clear language, illustrations, and provide helpful context to explain the theory's ideas.

## Execution Steps
1. **Context Checkout**: Run the bash command above to obtain the existing theory, adherence reviews, and literature reviews using `context_manager.py`.
2. **Check Adherence Reviews**: Read all adherence reviews in `<CONTEXT_DIR>/reviews/*/review.md` and check if any of them raise adherence issues or explanatory gaps.
   - If no issues are raised by the reviews, stop here. Simply report back the original theory ID from your inputs, together with a note that no changes were needed. You DO NOT need to read the `theory.md` or store a new result in this case. Simply report your input theory ID back unchanged.
3. **Theory Review**: Read `<CONTEXT_DIR>/theory/theory.md`, and (if present) each existing literature review `<CONTEXT_DIR>/literature/*/summary.md` to understand the theory and any prior literature grounding.
4. **Refinement Strategy**:
   - For each adherence and explanatory gap raised in the adherence review, identify the necessary updates to the theory's assumptions, constraints, or models. Determine what additions, generalizations, or new lemmas are needed (if any) to expand the explanatory coverage to cover the entire described phenomenon. In extreme cases, a complete restructuring of the theory may be needed.
5. **Validation**: Test your updates mathematically or via experiments, using the `run-experiment` skill.
6. **Reporting**: Edit the theory in `<OUTPUT_DIR>/theory.md` to apply your improvements.
7. **Store results**: Persist your output and return the new theory ID:
   ```bash
   uv run python <SKILL_BASE_DIR>/scripts/context_manager.py store_results --from_agent_type improve-adherence --from_folder <OUTPUT_DIR> --parent_theory <THEORY_ID>
   ```
   Note down the returned theory ID (e.g. `T_20260414_150000_x1y2z3`) as the result of this skill and include it in your final message.
