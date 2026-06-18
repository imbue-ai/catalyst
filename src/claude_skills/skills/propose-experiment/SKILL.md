---
name: propose-experiment
description: "Design and propose the next step: either a regular data-gathering experiment, literature research, or a concrete solution candidate."
argument-hint: "interpretations log ID (e.g. I_20260616_123456_abcdef)"
---

# Propose Experiment / Next Step

This skill is used to design and propose a single, high-value, and cost-effective next step to advance the research goal. 

## Mandate & Proposal Types
You must select and propose one of three types of proposals based on your current understanding of the research goal:

1. **Regular Experiment**: 
   - Use this to gather data, establish baselines, or test assumptions when more exploration is needed.
   - **Required Heading in `proposal.md`**: `# Experiment Proposal: <title>`
   - **Output Files**: `proposal.md` detailing motivation, experimental setup, expected outputs, and companion executable Python script `script.py` set up to run the experiment.

2. **Literature Research**: 
   - Use this to search and explore existing literature.
   - **Required Heading in `proposal.md`**: `# Literature Search Proposal: <title>`
   - **Output Files**: Only `proposal.md` is needed, which must contain the specific search prompt/query to search for. No `script.py` is needed.

3. **Solution Candidate**: 
   - *When you have gathered enough understanding to take a stab at solving the goal, emit a solution proposal.*
   - **Required Heading in `proposal.md`**: `# Solution Candidate Proposal: <title>`
   - **Output Files**: `proposal.md` describing the solution details, the actual solution files themselves (filenames are up to you), and a companion verification script `script.py` containing code to *verify* the solution.
   - **Verification Instructions**: You must read the `verification_instructions.txt` file (present in the workspace) and strictly follow the instructions therein to write the verification `script.py`.

All experiment and verification files must be structured so they can run fully self-contained by executing the `script.py` file.

## Input
Arguments: $ARGUMENTS

The arguments contain an interpretations log ID (like `I_...`). Parse this ID from the arguments.

## Folder Setup
All commands must be run in the current working directory. Do not `cd` anywhere else, and do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up two folders — one for the input context, one for your own output:
- `CONTEXT_DIR`: `mktemp -d -p ./tmp propose-experiment-context-XXXX`
- `OUTPUT_DIR`: `mktemp -d -p ./tmp propose-experiment-output-XXXX`

Run this command to populate the context, which retrieves the interpretations log from the database:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context \
    --for_agent_type propose-experiment \
    --target_folder <CONTEXT_DIR> \
    --from_interpretations <I_ID>
```

- `<CONTEXT_DIR>/interpretations/` — contains `interpretations.md` (read-only historical log).
- `<OUTPUT_DIR>/` — write your proposal files (`proposal.md`, and optional `script.py` / solution files) here.

---

## Execution Steps

1. **Context Checkout**: Run the `create_context` bash command above to retrieve the interpretations log from the database.
2. **Review Historical Log**: Read `<CONTEXT_DIR>/interpretations/interpretations.md` to identify knowledge gaps, uncertainties, or promising parameters.
3. **Determine Proposal Type**: Decide whether to propose a **Regular Experiment**, **Literature Research**, or **Solution Candidate** based on your current progress.
4. **Draft Proposal Document**: Write a document named `proposal.md` (this exact filename is required) in your `<OUTPUT_DIR>/`. Ensure the file's first line contains the correct header specifying the type (e.g. `# Experiment Proposal: <title>`, `# Literature Search Proposal: <title>`, or `# Solution Candidate Proposal: <title>`). Include:
   - **Motivation**: Why this step is important.
   - **Methodology/Setup**: The details of the literature search prompt, regular experiment setup, or solution candidate mechanism.
   - **Verification / Expected Outputs**: How results will be observed or verified.
5. **Write Companion / Verification Script**:
   - For an **Experiment** or **Solution Candidate**, write a companion, fully self-contained Python script named `script.py` in the same `<OUTPUT_DIR>/` folder.
   - For a **Solution Candidate**, you must open and read the `verification_instructions.txt` file in the current working directory, and follow those instructions to write the verification `script.py`.
   - The script must hard-code all parameters and not rely on command-line arguments or environment variables.
   - It must write all outputs (such as plots, logs, and metrics) directly to its current working directory.
6. **Store Results**: Persist the proposal files to the database. You must include the appropriate `--metadata proposal_type=<type>` (where `<type>` is `experiment`, `literature-search`, or `solution-candidate`) so the context manager records the correct metadata tag:
   ```bash
   uv run python <SKILL_BASE_DIR>/scripts/context_manager.py store_results \
       --from_agent_type propose-experiment \
       --from_folder <OUTPUT_DIR> \
       --parent_interpretations <I_ID> \
       --metadata proposal_type=<type>
   ```
   *Note down the returned proposal ID (e.g., `O_20260616_123456_abcdef`) as the result of this skill.*
