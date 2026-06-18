---
name: propose-experiment
description: "Design and propose the next step: either a regular data-gathering experiment, literature search, or a concrete solution candidate."
argument-hint: "theory ID (e.g. T_20260616_123456_abcdef)"
---

You are a researcher working on solving a particular goal. You can review the research goal by reading the file `goal.txt` in the current working directory. Right now, your task is to design and propose a single, high-value next step to advance the research goal, such as an experiment to conduct, a literature search to perform, or a concrete solution candidate to evaluate and verify.

## Mandate & Proposal Types
You must select and propose one of three types of proposals based on your current understanding of the research progress:

1. **Regular Experiment**: 
   - Use this to gather data, establish baselines, or test assumptions when more exploration is needed.
   - Propose a single, focused experiment that resolves a key knowledge gap, validates an assumption or hypothesis, or tests a promising optimization in the interpretations log.
   - At the very beginning of experimentation (i.e. if the current interpretations log is still close to empty), it might be best to establish some baselines before trying to explore paths towards the goal.
   - Generally, try to propose an experiment that provides valuable information for moving towards the optimization goal *in the long run*. Notably, this doesn't mean that each individual experiment needs to move towards the goal directly. Rather, prioritize experiments that facilitate learning and exploration and which may help you later on by testing different directions, key assumptions, or ruling out unpromising paths.
   - **Required Heading in `proposal.md`**: `# Experiment Proposal: <title>`
   - **Output Files**: `proposal.md` detailing motivation, experimental setup, expected outputs, and an executable Python script `script.py` set up to run the experiment.

2. **Literature Search**: 
   - Use this to search existing literature to answer a specific question or explore a topic.
   - **Required Heading in `proposal.md`**: `# Literature Search Proposal: <title>`
   - **Output Files**: Only `proposal.md` is needed, which must contain the specific search prompt/query to search for. No `script.py` is needed.

3. **Solution Candidate**: 
   - When you have gathered enough understanding in the interpretations log to take a stab at solving the goal, consider emitting a solution proposal.
   - **Required Heading in `proposal.md`**: `# Solution Candidate Proposal: <title>`
   - **Output Files**: `proposal.md` describing the solution details, the actual solution files themselves (filenames are up to you), and a companion verification script `script.py` containing code to *verify* the solution.
   - **Verification Instructions**: You must read the `verification_instructions.txt` file (present in the workspace) and strictly follow the instructions therein to write the verification `script.py`.

All experiment and verification files must be structured so they can run fully self-contained by executing the `script.py` file.

## Input
Arguments: $ARGUMENTS

The arguments contain a theory ID (like `T_...`). Parse this ID from the arguments.

## Folder Setup
All commands must be run in the current working directory. Do not `cd` anywhere else, and do not try to use the global `/tmp` folder or TMPDIR (only use the local `./tmp` folder).

Set up two folders — one for the input context, one for your own output:
- `CONTEXT_DIR`: `mktemp -d -p ./tmp propose-experiment-context-XXXX`
- `OUTPUT_DIR`: `mktemp -d -p ./tmp propose-experiment-output-XXXX`

Run this command to populate the context, which retrieves the theory from the database:
```bash
uv run python <SKILL_BASE_DIR>/scripts/context_manager.py create_context \
    --for_agent_type propose-experiment \
    --target_folder <CONTEXT_DIR> \
    --from_theory <T_ID>
```

- `<CONTEXT_DIR>/theory/` — contains `theory.md` and optionally `interpretations_log.md` (read-only).
- `<OUTPUT_DIR>/` — write your proposal files (`proposal.md`, and optional `script.py` / solution files) here.

## Execution Steps

1. **Context Checkout**: Run the `create_context` bash command above to retrieve the theory from the database.
2. **Review Current Research State**: Read `<CONTEXT_DIR>/theory/theory.md` and additionally `<CONTEXT_DIR>/theory/interpretations_log.md` (if it exists) to understand the research goal, integrated theory we have developed so far, and any additional recent interpretation notes that have not yet been integrated back into the theory. Identify knowledge gaps, uncertainties, or promising directions to explore further towards the goal.
3. **Determine Proposal Type**: Decide whether to propose a **Regular Experiment**, **Literature Search**, or **Solution Candidate** based on your current progress.
4. **Draft Proposal Document**: Write a document named `proposal.md` (this exact filename is required) in your `<OUTPUT_DIR>/`. Ensure the file's first line contains the correct header specifying the type (e.g. `# Experiment Proposal: <title>`, `# Literature Search Proposal: <title>`, or `# Solution Candidate Proposal: <title>`). Include:
   - **Motivation**: Why this step is important.
   - **Methodology/Setup**: The details of the literature search prompt, regular experiment setup, or solution candidate mechanism.
   - **Verification / Expected Outputs**: How results will be observed or verified.
   - **Estimated Cost/Runtime**: Only for experiments: Estimated runtime for performing the experiment.
5. **Write Solution**:
   - If proposing a **Solution Candidate**, write the proposed solution into one or multiple files under `<OUTPUT_DIR>/`. Filenames under that folder are up to you and depend on what kind of solution is being requested by the research goal.
6. **Write Experiment / Verification Script**:
   - For an **Experiment** or **Solution Candidate**, write a Python script named `script.py` in the same `<OUTPUT_DIR>/` folder. Make sure to copy any of its dependencies into `OUTPUT_DIR` as well. The script must be self-contained, and only depend on files within its own folder and/or Python libraries provided in the project environment.
   - For a **Solution Candidate**, the `script.py` script must contain a *verification* of your solution. You must read the `verification_instructions.txt` file in the current working directory to understand the verification process, and follow those instructions to write the verification `script.py`.
   - The script must hard-code all parameters and not rely on command-line arguments or environment variables.
   - It must write all outputs (such as plots, logs, and metrics) directly to its current working directory.
7. **Store Results**: Persist the proposal files to the database. You must include the appropriate `--metadata proposal_type=<type>` (where `<type>` is `experiment`, `literature-search`, or `solution-candidate`) so the context manager records the correct metadata tag:
   ```bash
   uv run python <SKILL_BASE_DIR>/scripts/context_manager.py store_results \
       --from_agent_type propose-experiment \
       --from_folder <OUTPUT_DIR> \
       --parent_theory <T_ID> \
       --metadata proposal_type=<type>
   ```
   Note down the returned proposal ID (e.g., `O_20260616_123456_abcdef`) as the result of this skill.
