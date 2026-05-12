# Quickstart Guide

This guide provides a high-level overview of the AI Scientist project and explains how to get started.

## Overall Structure

The AI Scientist is an automated system for generating, evaluating, and refining scientific theories. From a user's perspective, the system revolves around **Workflows**.

- **Workflows**: You initiate a workflow by providing a scientific phenomenon or an initial idea. The orchestrator then manages a sequence of steps, often involving parallel execution of specialized agents (e.g., for literature review, exploration, or theory generation).
- - **Add-on Steps**: In addition to standard workflows, you can manually extend any task by adding individual **Add-on Steps** (e.g., to specifically streamline or falsify a theory). This provides flexibility to guide the research process beyond the predefined workflow structures.
- **Theories and Artifacts**: Each step in a workflow generates artifacts, such as literature reviews, exploration reports, and, most importantly, theories.
- **Context Database**: All artifacts are stored in a persistent context database (`.ai-scientist-db`). This allows agents to reference previous work and enables the system to track the evolution of theories.

## Environment Templates

The AI Scientist uses specialized environments to run experiments and validate hypotheses. When a new task or step is initialized, the system uses `create_environment.py` to set up a dedicated working directory.

A **Template** is a directory that contains the base files, scripts, and configurations required for a specific type of scientific exploration. When creating an environment, you can specify a `--template` path, and the system will copy the template's contents into the new environment.

### What to Include in a Template

To provide the best possible starting point for an automated scientist, a template should typically include:

- **Custom Instructions (`CLAUDE.md` and `GEMINI.md`)**: Use these files to specify high-level goals, provide context on the phenomenon being researched, and give specific guidance on how to use the available tools and scripts.
- **Experiment Scripts**: Include pre-existing Python packages or scripts that the agent can use to run simulations, train models, or analyze data (e.g., a `shallow_mlps` folder with a CLI for running MLP experiments).
- **Project Configuration**: A `pyproject.toml` file with the necessary dependencies and tool settings for the specific research area. It's best to use `default_environment_pyproject.toml` as a baseline to make sure all dependencies needed for running the required scripts `context_manager.py` and `run_experiment.py` are included.
- **Foundational Literature**: Include key papers or reference documents (e.g., `.pdf` files) that define the research paradigm and style. Instruct the agent in `CLAUDE.md`/`GEMINI.md` to review these at the start of a task.
- **Example Commands**: Provide concrete examples of how to run common experiments in the instruction files.

This structured environment ensures that the agent has all the domain-specific knowledge and tools needed to perform rigorous scientific work from the outset.

## Walkthrough: Autonomous Theory Discovery

(Placeholder: A detailed walkthrough of running a workflow will be added here.)


## Walkthrough: Manual Workflow

(Placeholder: A detailed walkthrough of running a workflow will be added here.)