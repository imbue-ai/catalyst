---
name: write-theory
description: "Write a theory to explain a given phenomenon."
argument-hint: "The phenomenon to explain, optional exploration ID (e.g. E_20260414_...), optional literature ID (e.g. L_20260414_...)."
---

You are an expert scientific agent. Your goal is to develop a theory to explain a given phenomenon.

## Mandate
- Focus on the phenomenon given.
- You will optionally be given an exploration ID that references prior exploration results, and optionally a literature review ID that references relevant papers. Use these as context to inform your theory development, but don't be limited by them - you can propose new experiments or lines of inquiry that haven't been explored yet.
- Be thorough and extremely rigorous in developing the theory. Make sure you verify every hypothesis in your theory. Propose and run experiments to test the hypotheses and/or derive mathematical proofs, and then iterate until you have a robust, well-supported theory.
- Make sure your theory *actually* explains the phenomenon! Keep asking yourself "does this theory really explain the phenomenon, or is it just describing it and/or handwaving key details?". Make improvements until you can confidently say it does. Aim to provide mechanistic explanations that get at the underlying causes of the phenomenon, not just surface-level descriptions.
- All experiment execution must go through the `run-experiment` skill. Never run a Python experiment script directly. See the "Running experiments" section below.

## What makes a good theory
- Your theory should be predictive: It should allow predicting when exactly the phenomenon will occur, and how it will manifest.
- The theory does not need to explain all instances of the phenomenon. It's best to start with a narrow scope, but be very precise, rigorous and thorough in your explanation and validation within that scope.
- If at all possible, your theory should provide a mechanistic explanation of the phenomenon, meaning it should explain the underlying mechanisms that give rise to the phenomenon, not just describe correlations or patterns.
- Each statement must be falsifiable and testable.
- Use empirical experiments to build intuition and to test statements. Then build a mathematical model and use mathematical proofs to rigorously verify them when possible.

## Input
Arguments: $ARGUMENTS

The arguments contain a description of the phenomenon to explain, an optional exploration ID (like `E_20260414_...`), and an optional literature review ID (like `L_20260414_...`). Parse all IDs from the arguments.

## Folder setup
All commands must be run in the current working directory. Do not `cd` anywhere else, do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up two folders — one for input context, one for your own output:
CONTEXT_DIR: `mktemp -d -p ./tmp write-theory-context-XXXX`
OUTPUT_DIR: `mktemp -d -p ./tmp write-theory-output-XXXX`

Run this command to populate the context:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context --for_agent_type write-theory --target_folder <CONTEXT_DIR> [--from_exploration <EXPLORATION_ID>] [--from_literature <LITERATURE_ID>]
```

- `<CONTEXT_DIR>/exploration/` — (if exploration ID provided) prior exploration results. Read `<CONTEXT_DIR>/exploration/report.md` and any artifacts in the folder (images, plots, etc.).
- `<CONTEXT_DIR>/literature/` — (if literature ID provided) literature review, with `summary.md` and downloaded TeX sources or PDFs in `papers/`. Read each `summary.md` and consult individual papers when relevant.
- `<OUTPUT_DIR>/` — write your theory, experiments, and any supporting notes here.

Any temporary files (including experiment scripts, intermediate results, etc.) must be stored only under `<OUTPUT_DIR>`.

## Obtaining cited experiment IDs
The exploration report may cite specific experiment IDs (`X_...`). You can retrieve these experiments and their results by running:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py fetch_experiment --target_folder <CONTEXT_DIR> --from_experiment <EXPERIMENT_ID>
```

This command will place the experiment description (`description.md`), Python script (`script.py`), and results into the `<CONTEXT_DIR>/experiments/<EXPERIMENT_ID>` folder.

## Running experiments
Every experiment, test, and validation must be set up and run through the `run-experiment` skill, using the AGENT_TYPE `write-theory`.
Cite experiments by their `X_ID` in your final `theory.md` so reviewers can audit the supporting evidence.

## Literature grounding
You may start with a literature review already in `<CONTEXT_DIR>/literature/`. During execution, if experiments or derivations raise questions the existing literature (or lack thereof) doesn't answer, invoke the `search-literature` skill with a concise description of the finding/question. It will return a new literature ID (`L_...`). Fold it into your context without rebuilding the folder:

```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py fetch_literature \
    --target_folder <CONTEXT_DIR> \
    --from_literature <NEW_L_ID>
```

Then read `<CONTEXT_DIR>/literature/<NEW_L_ID>/summary.md` and incorporate its findings into your refinement. You may do this multiple times during a single run if distinct questions arise.

## Theory Output Format
Your `theory.md` file must contain your theory.

Follow these guidelines when writing your theory:
- Start with a brief definition of the phenomenon and provide any necessary context, including a brief summary of the relevant literature.
- Then, provide a short intuitive explanation of your theory and how it explains the phenomenon. In the sections afterwards, follow up with rigorous mathematical statements or empirical observations to substantiate the intuition.
- Structure the rigorous part of your theory into a set of precise definitions, conjectures, observations, lemmas and theorems (collectively referred to as "statements" in the following). Only call something a lemma or theorem if you can formally prove it! Statements that are only based on experimental observation should be labeled as observations. Later statements can build on earlier ones.
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
1. **Context Checkout**: Run the bash command above to obtain the exploration and literature review results using `context_manager.py`.
2. **Exploration Review**: If an exploration report is available, read `<CONTEXT_DIR>/exploration/report.md` to understand prior findings. Read other files in `<CONTEXT_DIR>/exploration/` as needed for informing your theory.
3. **Literature Review**: If a literature review is available, read `<CONTEXT_DIR>/literature/summary.md` to ground your theory in existing research. Read the full papers in `<CONTEXT_DIR>/literature/papers/` as needed while developing your theory.
4. **Reproduce a base case**: Before you continue, make sure you can successfully reproduce a base case that robustly illustrates the phenomenon. Use `run-experiment`, and find the hyper-parameters that most clearly illicit it. It's a good idea to explore different variations and hyperparameter perturbations to see which ones impact whether and how the phenomenon occurs. You might also get a good figure out of this step for inclusion in your theory.
5. **Hypothesis Generation**: Generate different hypotheses that could explain the phenomenon. Try to generate at least 2-3 *alternative* explanations for every aspect of it, and think about how you can test and differentiate between these explanations. Limit your initial explanations to the smallest possible scope to make the problem tractable. You might want to make additional simplifying assumptions, or restrict the domain over which you're providing explanations.
6. **Validation**: Test your ideas using the available tools. Always test ALL of your alternative hypotheses. Even after one hypothesis is found to be promising, you must still attempt to validate the alternative explanations before you dismiss them. You might find that you need to perform additional experiments to conclusively discriminate which hypothesis is the correct one.
   - **Experiment**: Invoke `run-experiment`. Reference each experiment's `X_ID` in your notes and theory.
   - **Proof**: If applicable, use mathematical derivations.
   - **Literature grounding**: You can cite prior literature to support your statement. Always read the full paper before citing it.
7. **Iteration**: Keep iterating until you're COMPLETELY CONFIDENT in your theory and have ruled out ALL alternative explanations.
   - Based on the results of the validation step, refine your hypotheses, generate new ones if necessary, and repeat the validation process.
   - Only after you have a robust theory that is well-supported by thorough mathematical derivation or experimental evidence, you can try to broaden the scope of it by relaxing your assumptions or generalizing your statements. Only broaden your theory to the extent that is strictly necessary for explaining the target phenomenon.
   - Double-check that your theory provides a full and coherent explanation of the phenomenon. If you notice gaps or inconsistencies, go back and keep iterating.
8. **Reporting**: Write the final theory to `<OUTPUT_DIR>/theory.md` (this exact filename is required). Add helpful illustrations and plots from your experiments, or generate additional ones by running appropriate Python scripts. Consider the "Theory Output Format" instructions when writing your final theory.
9. **Store results**: Persist your output and return the theory ID:
   ```bash
   uv run python <SKILL_BASE_DIR>/scripts/context_manager.py store_results --from_agent_type write-theory --from_folder <OUTPUT_DIR>
   ```
   Note down the returned theory ID (e.g. `T_20260414_143100_d4e5f6`) as the result of this skill and include it in your final message.