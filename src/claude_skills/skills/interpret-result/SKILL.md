---
name: interpret-result
description: "Interpret the results of newly run experiments, literature searches, or solution candidates, and append the findings as new sections to the interpretations log inside the theory folder."
argument-hint: "theory ID and one or more result IDs (e.g. T_20260616_123456_abcdef X_20260616_123456_abcdef L_20260616_123456_abcdef)"
---

# Interpret Result

We are performing research to solve the goal described in the file `goal.txt`. As part of this research, we have been running experiments, literature searches, and designing solution candidates. Some new results have become available from one or more completed processes (experiments, literature searches, or solution candidates). Your goal is to interpret these results and append your interpretations and conclusions to the central interpretations log.

## Mandate
- Keep interpretations objective and strictly supported by empirical observations or literature findings. Avoid over-generalizing or jumping to unsupported conclusions.
- Do not modify or overwrite any historical sections of the interpretations log; only append the new sections under new headers, with exactly one section for each input result.

## Input
Arguments: $ARGUMENTS

The arguments contain a theory ID (like `T_...`) and one or more result IDs (like `X_...` for experiments, `L_...` for literature searches, or `U_...` for solution candidates). Parse all IDs from the arguments.

## Folder Setup
All commands must be run in the current working directory. Do not `cd` anywhere else, and do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up two folders — one for the input context, one for your own output:
- `CONTEXT_DIR`: `mktemp -d -p ./tmp interpret-result-context-XXXX`
- `OUTPUT_DIR`: `mktemp -d -p ./tmp interpret-result-output-XXXX`

Run this command to populate the context, which retrieves the theory and result artifacts from the database:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context \
    --for_agent_type interpret-result \
    --target_folder <CONTEXT_DIR> \
    --from_theory <T_ID> \
    [--from_experiment <X_ID_1> --from_experiment <X_ID_2> ...] \
    [--from_literature <L_ID_1> --from_literature <L_ID_2> ...] \
    [--from_solution <U_ID_1> --from_solution <U_ID_2> ...]
```
*Make sure to repeat the `--from_experiment`, `--from_literature`, and `--from_solution` flags for all corresponding IDs parsed from the arguments.*

Initialize your output directory with the current theory folder files:
```bash
cp -r "<CONTEXT_DIR>/theory/"* "<OUTPUT_DIR>/"
```

- `<CONTEXT_DIR>/theory/` — contains `theory.md` and optionally `interpretations_log.md` (read-only historical logs).
- `<CONTEXT_DIR>/results/experiments/<X_ID>/` — contains the experiment folder with `description.md` and all generated plots, logs, and CSV outputs (if experiment results were checked out).
- `<CONTEXT_DIR>/results/literature/<L_ID>/` — contains the literature search results folder with `summary.md` (if literature results were checked out).
- `<CONTEXT_DIR>/results/solutions/<U_ID>/` — contains the solution candidate folder with `solution.md` (if solution candidates were checked out).
- `<OUTPUT_DIR>/` — contains `theory.md` (which you must leave completely unchanged) and optionally `interpretations_log.md` which you will modify or create to append exactly one new section for each input result.

## Obtaining cited experiment IDs
Your inputs may cite specific experiment IDs (`X_...`). You can retrieve these experiments and their results by running:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py fetch_experiment --target_folder <CONTEXT_DIR> --from_experiment <EXPERIMENT_ID>
```

This command will place the experiment description (`description.md`), Python script (`script.py`), and results into the `<CONTEXT_DIR>/experiments/<EXPERIMENT_ID>` folder.

---

## Execution Steps

1. **Context Checkout**: Run the `create_context` bash command above to retrieve the historical theory folder and new results.
2. **Review Current Research State**: Read `<CONTEXT_DIR>/theory/theory.md` and additionally `<CONTEXT_DIR>/theory/interpretations_log.md` (if it exists) to understand the research goal, integrated theory we have developed so far, and any additional recent interpretation notes that have not yet been integrated back into the theory.
3. **Locate and Review Results**:
   - **Experiments**: Check `<CONTEXT_DIR>/results/experiments/<X_ID>/`. Read `description.md` and carefully inspect the generated files (plots, CSVs, logs, etc.).
   - **Literature Searches**: Check `<CONTEXT_DIR>/results/literature/<L_ID>/`. Read `summary.md` to find the summarized literature findings and search insights.
   - **Solution Candidates**: Check `<CONTEXT_DIR>/results/solutions/<U_ID>/`. Read `solution.md` (and any related files) to review the proposed solution candidate. The solution will have been validated through an experiment, mentioned in the `solution.md` file by its experiment ID (`X_...`). Please see the instructions above to obtain the cited experiment ID with its specific setup and results.
4. **Draft Interpretations**: Draft a new section *for each new result ID* passed as input:
   - State clearly what result type and ID are being interpreted.
   - Summarize the empirical observations (for experiments), the retrieved literature findings (for literature searches), or the proposed solution design (for solution candidates).
   - Detail the conclusions and interpretations drawn from these observations/findings, and outline remaining open questions or next steps.
   - You must write exactly one new markdown section under a new header for each input result:
     - For an experiment: `## Experiment <X_ID>: <Title>`
     - For a literature search: `## Literature Search <L_ID>: <Title>`
     - For a solution candidate: `## Solution Candidate <U_ID>: <Title>`
5. **Update Log**: Append these new sections to `<OUTPUT_DIR>/interpretations_log.md` (create the file if it does not exist, and only append to it, while leaving `<OUTPUT_DIR>/theory.md` unchanged).
6. **Store Results**: Persist the updated theory folder to the database:
   ```bash
   uv run python <SKILL_BASE_DIR>/scripts/context_manager.py store_results \
       --from_agent_type interpret-result \
       --from_folder <OUTPUT_DIR> \
       --parent_theory <T_ID>
   ```
   *Replace `<T_ID>` with the ID of the input theory, ensuring child-to-parent lineage mapping.*
