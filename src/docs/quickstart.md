# Quickstart Guide

This guide provides a high-level overview of the Catalyst project and explains how to get started.

## Overall Structure

Catalyst is an automated system for generating, evaluating, and refining scientific theories. From a user's perspective, the system revolves around **Workflows**.

- **Workflows**: You initiate a workflow by providing a scientific phenomenon or an initial idea. The orchestrator then manages a sequence of steps, often involving parallel execution of specialized agents (e.g., for literature review, exploration, or theory generation).
- - **Add-on Steps**: In addition to standard workflows, you can manually extend any task by adding individual **Add-on Steps** (e.g., to specifically streamline or falsify a theory). This provides flexibility to guide the research process beyond the predefined workflow structures.
- **Theories and Artifacts**: Each step in a workflow generates artifacts, such as literature reviews, exploration reports, and, most importantly, theories.
- **Context Database**: All artifacts are stored in a persistent context database (`.catalyst-db`). This allows agents to reference previous work and enables the system to track the evolution of theories.

## Environment Templates

Catalyst uses specialized environments to run experiments and validate hypotheses. When a new task or step is initialized, the system uses `create_environment.py` to set up a dedicated working directory.

A **Template** is a directory that contains the base files, scripts, and configurations required for a specific type of scientific exploration. When creating an environment, you can specify a `--template` path, and the system will copy the template's contents into the new environment.

### What to Include in a Template

To provide the best possible starting point for an automated scientific agent, a template should typically include:

- **Custom Instructions (`CLAUDE.md` and `GEMINI.md`)**: Use these files to specify high-level goals, provide context on the phenomenon being researched, and give specific guidance on how to use the available tools and scripts.
- **Experiment Scripts**: Include pre-existing Python packages or scripts that the agent can use to run simulations, train models, or analyze data (e.g., a `shallow_mlps` folder with a CLI for running MLP experiments).
- **Project Configuration**: A `pyproject.toml` file with the necessary dependencies and tool settings for the specific research area. It's best to use `default_environment_pyproject.toml` as a baseline to make sure all dependencies needed for running the required scripts `context_manager.py` and `run_experiment.py` are included.
- **Foundational Literature**: Include key papers or reference documents (e.g., `.pdf` files) that define the research paradigm and style. Instruct the agent in `CLAUDE.md`/`GEMINI.md` to review these at the start of a task.
- **Example Commands**: Provide concrete examples of how to run common experiments in the instruction files.

This structured environment ensures that the agent has all the domain-specific knowledge and tools needed to perform rigorous scientific work from the outset.

## Walkthrough: Autonomous Theory Discovery

In this walkthrough, we will utilize the "Develop a Theory" workflow to have Catalyst autonomously develop a theory to explain a given phenomenon.

1. Click the plus icon to start a new research project
   
   ![plus icon](start_research_plus.png)

2. Select the "Develop a Theory" workflow. Then type in the phenomenon that you want to discover a theory for. You can optionally select the agent harness and model to use. The Evolution-based workflow builds a population of possible theories in order to avoid dead ends and early hypothesis collapse. However, it can take a long time and can be quite expensive to run. The Linear workflow instead explores a single explanation, which may be sufficient for simpler problems.
   
   ![start research](start_research_phenomenon.png)

3. No matter whether you pick the evolution-based or linear workflow, Catalyst will begin with a literature review and perform an initial exploration of the problem space. It will then continue to form an initial theory (for evolution: n alternative theories) that attempts to explain the phenomenon. Each step might involve running multiple experiments and/or performing mathematical derivations. After the initial theory writing, the linear theory development workflow will enter a loop of repeated review & refinement. The evolution-based workflow will also perform successive review & refinement cycles, but will do so using randomized sampling from a population of *scored* theories.
   
   ![workflow](workflow.png)

4. Click on any completed step to inspect its results. Most steps generate one or multiple artifacts, represented by a unique ID. You can click on these IDs to inspect them within the built-in markdown viewer, print them as a PDF, or export them as a .zip file.
   
   ![artifact](artifact.png)

5. Once the workflow completes, you can find the final theory in the result of the final refinement step (for the linear workflow), or look at the population of scored theories in the "Theories" tab (for the evolution-based workflow).
   
   ![theories tab](theories_tab.png)

6. You can pause the research at any time and resume it later. Note that any currently running agents will need to start over when resuming a paused research task. Or you can click the "Add step" icon at the bottom of the workflow to add additional iterations and/or individual steps after the main workflow has completed.
   
   ![add step icon](add_step_icon.png)


## Walkthrough: Manual Workflow

In this walkthrough, we will import an existing theory, and use Catalyst to perform different custom steps.

1. Click the plus icon to start a new research project
   
   ![plus icon](start_research_plus.png)

2. Select "Existing Theory Draft" and select the "Import" workflow. You can provide a .pdf, .tex or .md file that contains your pre-existing theory draft. You can also upload a .zip file containing a Markdown or LaTeX file together with any associated images.
   
   ![start research](start_research_import.png)

3. Once the import step is complete, click the "Add Step" icon.
   
   ![add step icon](add_step_icon.png)
   
4. Select "Theory" and "Review Theory" to perform an full review of the current theory. Select the imported theory as the target. The Review Theory step will attempt to falsify any statement within the current theory, and also look for directions for generalizing and/or expanding the theory at hand. It produces multiple review reports, which you can inspect by first clicking on the completed review theory step in the workflow, and then clicking on one of the generated review IDs in the step's results on the right.
   
   ![add review](add_review.png)

   ![review results](review_results.png)

5. Next, once the review step has completed, we will ask Catalyst to try and address the issues found by the review step. Add another step. This time, check the "...which has already been reviewed" toggle under "Theory", and then find the "Refine Theory" add-on. Select the target theory, and confirm. The Refine theory step will generate a new theory ID that contains the new, updated theory.
   
   ![add refine](add_refine.png)
   
6. You can also provide manual instructions for editing a theory. To do this, click "Add Step", and find the "Edit Theory" add-on. Under "Configuration", provide a custom instruction that describes the change you'd like Catalyst to perform. For example, you can ask "Add additional figures to illustrate the derivations in a visual way". Make sure that you select the correct target theory that corresponds to the final result from the theory refinement step. (The most recently generated theory ID should already be selected by default).
   
   ![add edit](add_edit.png)

7. Click on the generated theory ID to view it inline, use the print icon to generate a PDF (browser support required), or download a .zip file containing the markdown and required image files.
   
   ![artifact](artifact_2.png)