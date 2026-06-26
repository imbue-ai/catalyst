---
name: integrate-interpretations
description: "Integrate recent interpretations from the interpretation log into the associated theory."
argument-hint: "theory ID, and optionally whether to branch into two distinct theories"
---

You are an expert scientific agent. We are working on a theory in order to solve a particular research goal. Recently, some additional data has become available (such as experiment results, new literature findings, or competing solution candidates). Your current task now is to update your theory to integrate the new insights from these recent findings.

## Mandate
- The resulting `theory.md` file should encompass the entirety of your research progress and current best understanding so far.
- Sometimes, new results and interpretations may conflict with your existing understanding. In such cases, be extra rigorous in reviewing the new evidence, comparing it to previous evidence mentioned in the theory, and try to reconcile any contradictions. You should update and/or remove previous statements from the theory if they are no longer consistent with the overall body of evidence.

## Input
Arguments: $ARGUMENTS

The arguments contain a theory ID (like `T_20260414_...`). Parse the theory ID from the arguments.
It might additionally contain an instruction to indicate that you should BRANCH into two distinct theories.

## Folder setup
All commands must be run in the current working directory. Do not `cd` anywhere else, do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up two folders — one for input context, one for your own output:
CONTEXT_DIR: `mktemp -d -p ./tmp integrate-interpretations-context-XXXX`
OUTPUT_DIR: `mktemp -d -p ./tmp integrate-interpretations-output-XXXX`

Run this command to populate the context, and then initialize the output folder with the original theory files:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context \
    --for_agent_type integrate-interpretations \
    --target_folder <CONTEXT_DIR> \
    --from_theory <THEORY_ID>
cp -r "<CONTEXT_DIR>/theory/"* "<OUTPUT_DIR>/"
```

- `<CONTEXT_DIR>/theory/` — the original theory (read-only input). Read `<CONTEXT_DIR>/theory/theory.md`, `<CONTEXT_DIR>/theory/interpretation_log.md`, and any artifacts.
- `<OUTPUT_DIR>/` — write your updated theory, experiments, and any supporting notes here.

## Obtaining cited experiment IDs
Your inputs may cite specific experiment IDs (`X_...`). You can retrieve these experiments and their results by running:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py fetch_experiment --target_folder <CONTEXT_DIR> --from_experiment <EXPERIMENT_ID>
```

This command will place the experiment description (`description.md`), Python script (`script.py`), and results into the `<CONTEXT_DIR>/experiments/<EXPERIMENT_ID>` folder.

## Obtaining cited solution IDs
Your inputs may cite specific solution IDs (`U_...`). You can retrieve these solutions and their contents by running:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py fetch_solution --target_folder <CONTEXT_DIR> --from_solution <SOLUTION_ID>
```

This command will place the solution candidate description (`solution.md`) and any related files into the `<CONTEXT_DIR>/solutions/<SOLUTION_ID>` folder.

## Theory Output Format
Your `theory.md` file must be: A revised theory that integrates the new interpretations from the interpretation log.

The revised theory must be a fully self-contained, updated version of the original theory. Do NOT add any notes inside the file about the adherence review or the improvement process itself. The file should read like a standalone document that presents the final improved theory.

Please maintain the following guidelines for the improved theory:
- Start with including the current research goal itself. You can always rever back to the file `goal.txt` in the current working directory to read the research goal again if you need to.
- Structure the main part of your theory as a set of key observations and insights. For each, cite supporting evidence (such as experiment IDs `X_...`, literature citations, or mathematical reasoning). For each observation or insight, add a tag that expresses your confidence in that statement as high, medium, or low, depending on the strength of the evidence that has been seen so far. Be conservative in your confidence assessments: Typically, you'll need many independent experiments or at least one reliable literature source to warrant a confidence level that's medium or high!
- Feel free to organize the observations and insights into logical subsections, tables, or other types of groupings to improve the readability and brevity of the theory.
- After the main part, add two sections subsectionsthat express: 1. open questions and uncertainties (e.g. unresolved contradictions in the evidence, areas where evidence is still lacking, or important knowledge gaps that remain), and 2. a "Research Plan" section in which you lay out your current ideas and plans to move further towards solving the stated goal.
- When integrating solution candidates from the interpretation log, keep track of the highest-potential solution candidate seen so far in a short separate section of the theory. Include its solution ID (`U_...`) and verification experiment ID (`X_...`) for easy lookup.
- Image references in the markdown file need to be relative to `<OUTPUT_DIR>`. NEVER use absolute paths. Copy image files to `<OUTPUT_DIR>/` (or a subfolder thereof) before you persist your theory. Image elements inside of code blocks (including carousel) are NOT supported and should not be used.
- Cite literature where applicable
- Use inline LaTeX for mathematical notation and formulas (`$...$` for inline math, and `$$...$$` for display math). Do NOT put formulas into code blocks.
- Keep the title of the theory representative of its current key direction. Update the title `# ...` whenever the direction of the theory has changed and its current title is no longer representative.

## Branching
*If* the input tells you to branch into two distinct theories, do this as follows:
1. First create the regular updated theory as usual, and save it to the database (this will capture the current state of `<OUTPUT_DIR>/theory.md` at the time).
2. If any of the new interpretations were contradictory or unclear, consider updating your second theory to express the opposite or alternative view.
3. Then, most importantly, come up with a second distinct "Research Plan" that is fundamentally different from your first one. Be bold here, and explore less-common approaches. Try to come up with novel ideas that go outside of the obvious directions and which are significantly different from anything tried so far! Consider going back to the drawing board, or taking big high-risk/high-reward bets, rather than just continuing with conservative, incremental steps.
4. Once you have updated the theory in `<OUTPUT_DIR>/theory.md`, save the second theory to the database as well.

## Execution Steps
1. **Context Checkout**: Run the bash command above to obtain the existing theory using `context_manager.py`.
2. **Review Current Theory and Interpretations**: Read `<CONTEXT_DIR>/theory/theory.md` and additionally `<CONTEXT_DIR>/theory/interpretation_log.md` to understand the research goal, current integrated theory we have developed so far, and the additional recent interpretation notes that have not yet been integrated back into the theory.
   - Special case: If the `interpretation_log.md` file does not exist or is empty, stop here. Simply report back the original theory ID from your inputs, together with a note that no changes were needed. You DO NOT need to read the `theory.md` or store a new result in this case. Simply report your input theory ID back unchanged.
3. **Refinement Strategy**:
   - For each new result in the `interpretation_log.md`, identify the necessary updates and additions to the theory's observations and conclusions. Especially look out for any conflicting statements or ideas that need to be revised. In extreme cases, a complete restructuring of the theory may be needed.
   - Check if, given the new interpretations, the confidence of any of the existing statements should be adjusted (either upwards or downwards).
   - Obtain cited experiment IDs as needed to review the experiment details and results to inform your revisions.
   - Then, revise the open questions and current ideas / plan sections in the theory based on the new information. Remove questions that have been answered, and add new questions or ideas that are emerging.
   - This is the time to consider whether the current research direction is still the most promising one, or if it has shown diminishing returns. Please zoom out and consider other approaches to achieve the goals and whether it might be worth a shot to switch to one of them, as radical as they might seem.
4. **Polish & Restructuring**: After you have made the necessary content updates, review the overall structure and flow of the theory. If any section has become too long or contains too many items, consider reorganizing the content into different (sub-)sections, adding new headings, combining similar items, organizing related items together into tables, or doing whatever else is needed to improve the readability and coherence of the document.
5. **Write Improvements**: Edit the theory in `<OUTPUT_DIR>/theory.md` to apply your improvements. Then, delete the `interpretation_log.md` file in `<OUTPUT_DIR>/` (or clear its contents) since all of the interpretations have now been integrated back into the theory.
6. **Store results**: Persist your output:
   ```bash
   uv run python <SKILL_BASE_DIR>/scripts/context_manager.py store_results --from_agent_type integrate-interpretations --from_folder <OUTPUT_DIR> --parent_theory <THEORY_ID>
   ```
   Note down the returned theory ID (e.g. `T_20260414_150000_x1y2z3`) as the result of this skill and include it in your final message.
7. **Branching (optional)**: If (and only if) you were instructed to branch into two distinct theories, come up with a second alternative theory, as described above in the section on Branching. You can edit the theory in `<OUTPUT_DIR>/theory.md` in-place. Make sure to update the title of the second theory to reflect its new direction. Then, run the previous step a second time to store the alternative theory in the database, and note down its returned theory ID (e.g. `T_20260414_150000_a1b2c3`) as well. In this case, you should return both theory IDs in your final message.
