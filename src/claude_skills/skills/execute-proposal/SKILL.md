---
name: execute-proposal
description: "Determine the type of proposal given, execute/delegate accordingly, and return the appropriate resulting ID (experiment ID, literature search ID, or solution ID)."
argument-hint: "proposal ID (e.g. O_20260616_123456_abcdef)"
---

As part of a larger research effort, you're in charge of executing a given proposal. The proposal may be one of three types: a regular experiment, a literature search, or a solution candidate.

## Input
Arguments: $ARGUMENTS

The arguments contain a single proposal ID (like `O_20260616_...`). Parse this ID from the arguments.

## Folder Setup
All commands must be run in the current working directory. Do not `cd` anywhere else, and do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up two folders — one for the input context, one for your own output:
- `CONTEXT_DIR`: `mktemp -d -p ./tmp execute-proposal-context-XXXX`
- `OUTPUT_DIR`: `mktemp -d -p ./tmp execute-proposal-output-XXXX`

Run this command to populate the context, which retrieves the proposal files from the database:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context \
    --for_agent_type execute-proposal \
    --target_folder <CONTEXT_DIR> \
    --from_proposal <PROPOSAL_ID>
```

- `<CONTEXT_DIR>/proposal/` — contains the read-only proposal files: `proposal.md`, and optional `script.py` / solution files.
- `<OUTPUT_DIR>/` — write your execution summary, results, or metadata here.

## Execution Steps
1. **Context Checkout**: Run the `create_context` bash command above to retrieve the selected proposal from the database.
2. **Determine Proposal Type**: Read `<CONTEXT_DIR>/proposal/proposal.md` and check its heading to determine the type of proposal (experiment, literature-search, or solution-candidate).
3. **Execute Flow**:
   - **For `"experiment"`**:
     - Copy all files from `<CONTEXT_DIR>/proposal/` into `<OUTPUT_DIR>/`. Rename `proposal.md` to `description.md`.
     - Invoke the `run-experiment` skill to execute the proposal script. Use the `--store_failures` flag to ensure that even failed experiments are stored to the database and assigned an experiment ID.
     - If the experiment fails due to a transient technical error, you can retry it. You can also perform minor syntactic or non-functional changes to its code to fix obvious bugs. However, never change the substance of the experiment! Just report the failed experiment result if it consistently fails or cannot be fixed through trivial changes.
     - Parse the resulting experiment ID (e.g. `X_20260616_123456_abcdef`) from the runner's output. Note it down as the result of this skill.
   - **For `"literature-search"`**:
     - Extract the specific search prompt from `proposal.md`.
     - Invoke the `search-literature` skill with that search prompt as the argument.
     - Parse and note the resulting literature review ID (e.g. `L_20260616_123456_abcdef`) as the result of this skill.
   - **For `"solution-candidate"`**:
     - Copy all files from `<CONTEXT_DIR>/proposal/` into `<OUTPUT_DIR>/`. Rename `proposal.md` to `description.md`.
     - Review the verification script of the solution candidate (`script.py`) and confirm that it adheres to any verification requirements given in `verification_instructions.txt` and/or `GUIDANCE.txt` (if any). If you notice any signs of reward-hacking, intentional result falsification, or non-adherence to the requirements, you must highlight those issues prominently in your `solution.md` output!
     - Invoke the `run-experiment` skill to execute the verification script (`script.py`) in `<OUTPUT_DIR>/`.
     - Parse the resulting verification experiment ID (e.g. `X_20260616_123456_abcdef`).
     - Create a `solution.md` file in `<OUTPUT_DIR>/`. Populate it with a detailed summary of the solution candidate, the results of the verification experiment (including its experiment ID `X_...`), and an assessment of how well the goal described in `goal.txt` was met by this solution candidate.
     - Find the parent theory ID (`T_...`) from the `proposal.md` file.
     - Store the results using `store_results`:
       ```bash
       uv run python <SKILL_BASE_DIR>/scripts/context_manager.py store_results \
           --from_agent_type execute-proposal \
           --from_folder <OUTPUT_DIR>
           --parent_theory <T_ID>
       ```
     - Parse and note the resulting solution ID (e.g. `U_20260616_123456_abcdef`) as the result of this skill.
4. **Report Results**: Report the resulting ID as the result of this skill.
