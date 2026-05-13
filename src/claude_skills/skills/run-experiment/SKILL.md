---
name: run-experiment
description: "Set up and run a single experiment. Experiments can be arbitrary Python scripts. All experiment execution must go through this skill."
user-invocable: false
---

## Experiment setup & execution steps
1. Create a new folder within your output directory for this experiment (e.g. `mkdir <OUTPUT_DIR>/experiment-<title>`).
2. Write a single, self-contained Python script called `script.py` that runs the experiment into the experiment folder.
  - The script should hard-code all parameters inside of it. It must not rely on any command-line arguments or environment variables.
  - It should write all outputs (plots, csvs, logs, etc.) under its current working directory. (The wrapper will `cd` into the experiment folder before executing the script).
  - It is fine for the script to import and/or delegate to shared libraries and scripts that exist in the workspace, but it should not rely on any other files that only exist in the caller's temp folder, context folder, or output folder.
3. Also write a `description.md` file in the experiment folder. The `description.md` must contain a complete description of what the experiment tests, its hard-coded parameter values (if any), and what outputs it produces.
4. Determine the context you're running the experiment in: Do you know the theory ID (e.g. `T_20260416_150000_a1b2c3`) that this experiment is motivated by (fine if not)? You should also have been given an AGENT_TYPE.
5. Execute the script through the following wrapper, passing the experiment folder and the parent theory ID if you have it:
```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/run_experiment.py --experiment_folder <EXPERIMENT_FOLDER_PATH> --agent_type <AGENT_TYPE> [--parent_theory <T_ID>]
```
  Invoke the `run_experiment.py` wrapper *synchronously*, not in the background! It already has a built-in timeout mechanism, so you don't need to worry about setting timeouts. Do NOT try to run experiments in parallel.
6. The wrapper will execute the script in EXPERIMENT_FOLDER_PATH, passing through its stdout and stderr. It will capture all experiment outputs and persist them to a database for record keeping. It will finish its output by printing a unique experiment ID (e.g. `X_20260416_150000_a1b2c3`) that can be used to retrieve the results later.

Some experiments may take a long time to complete (up to a few hours). Please allow enough time for the experiment to finish before assuming that it has failed.
NEVER execute your `script.py` directly or through any other wrapper. Always use the `run_experiment.py` wrapper as described above.

## Useful experiment patterns
- Have the experiment generate plots and visualizations of the data in addition to numerical output. Inspect the visualizations to gain a better intuition when analyzing the experiment's results and to check for any potential issues with the experiment setup. The plots may also provide useful illustrations to include in your report or theory.