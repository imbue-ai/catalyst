---
name: run-experiment
description: "Set up and run a single experiment. Experiments can be arbitrary Python scripts. All experiment execution must go through this skill."
allowed-tools: Bash(uv run:*) Bash(mkdir:*) Bash(ls:*) Read(*) Write(tmp/*) Edit(tmp/*)
user-invocable: false
---

## Experiment setup & execution steps
1. Create a new folder within your output directory for this experiment (e.g. `mkdir <OUTPUT_DIR>/experiment-<title>`).
2. Write a single, self-contained Python script called `script.py` that runs the experiment into the experiment folder.
  - The script should hard-code all parameters inside of it. It must not rely on any command-line arguments or environment variables.
  - It should and write all outputs (plots, csvs, logs, etc.) to its current working directory. (The wrapper will `cd` into the experiment folder before executing the script).
  - It is fine for the script to import and/or delegate to shared libraries and scripts that exist in the workspace, but it should not rely on any other files that only exist in the caller's temp folder, context folder, or output folder.
3. Also write a `description.md` file in the experiment folder. The `description.md` must contain a complete description of what the experiment tests, its hard-coded parameter values (if any), and what outputs it produces.
4. Determine the context you're running the experiment in: Do you know the theory ID (e.g. `T_20260416_150000_a1b2c3`) that this experiment is motivated by (fine if not)? You should also have been given an AGENT_TYPE.
5. Execute the script through the following wrapper, passing the experiment folder and the parent theory ID if you have it:
```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/run_experiment.py --experiment_folder <EXPERIMENT_FOLDER_PATH> --agent_type <AGENT_TYPE> [--parent_theory <T_ID>]
```
6. The wrapper will execute the script in EXPERIMENT_FOLDER_PATH, passing through its stdout and stderr. It will capture all experiment outputs and persist them to a database for later retrieval. It will finish its output by printing a unique experiment ID (e.g. `X_20260416_150000_a1b2c3`) that can be used to retrieve the results later.