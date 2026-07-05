# Workflows and Add-ons

This document describes the available workflows and add-on steps in the Imbue Catalyst orchestrator.

## Workflows

Workflows are high-level processes that orchestrate multiple steps to achieve a scientific goal.

### `develop-theory`
Generates and evolves multiple theories in parallel for a given phenomenon.
- **Inputs**:
    - `phenomenon`: A description of the phenomenon to explain.
    - `num_root_theories`: The number of initial theories to generate.
    - `evolve_iterations`: The number of evolution iterations to perform.
- **Stages**:
    1.  `summarize-title`: Summarizes the phenomenon into a short title.
    2.  `literature-review` & `explore`: Gathers background information and performs initial exploration.
    3.  `write-n-theories`: Generates the specified number of initial theories.
    4.  `review-theory`: Reviews each generated theory.
    5.  `score-theories`: Ranks and scores the theories.
    6.  `evolve-loop`: Repeatedly samples, mutates, reviews, and re-scores theories (with optional intermediate `summarize-research` steps).
    7.  `summarize-research`: Summarizes the current research status.

### `develop-theory-linear`
Generates a single theory and refines it iteratively.
- **Inputs**:
    - `phenomenon`: A description of the phenomenon to explain.
    - `max_refinements`: The maximum number of refinement iterations.
- **Stages**:
    1.  `summarize-title`: Summarizes the phenomenon.
    2.  `literature-review` & `explore` (parallel): Gathers background and explores.
    3.  `write-theory`: Generates an initial theory.
    4.  `refinement-loop`: Iteratively reviews and refines the theory (with optional intermediate `summarize-research` steps).
    5.  `summarize-research`: Summarizes the current research status.

### `refine-theory-idea`
Starts with a specific scientific idea and evolves it into a scored theory.
- **Inputs**:
    - `idea`: The initial scientific idea.
    - `file_path`: (Optional) Path to supporting files.
    - `evolve_iterations`: The number of evolution iterations.
- **Stages**:
    1.  `summarize-title`: Summarizes the idea.
    2.  `support-idea`: Develops the initial idea into a theory.
    3.  `review-theory`: Reviews the theory.
    4.  `score-theories`: Scores the theory.
    5.  `evolve-loop`: Evolves the theory (with optional intermediate `summarize-research` steps).
    6.  `summarize-research`: Summarizes the current research status.

### `refine-theory-idea-linear`
Starts with a specific idea and refines it iteratively.
- **Inputs**:
    - `idea`: The initial scientific idea.
    - `file_path`: (Optional) Path to supporting files.
    - `max_refinements`: The maximum number of refinements.
- **Stages**:
    1.  `summarize-title`: Summarizes the idea.
    2.  `support-idea`: Develops the idea into a theory.
    3.  `refinement-loop`: Iteratively reviews and refines the theory (with optional intermediate `summarize-research` steps).
    4.  `summarize-research`: Summarizes the current research status.

### `import-theory`
Imports an existing theory from a file into the system.
- **Inputs**:
    - `file_path`: Path to the theory file (.tex, .pdf, or .md).
- **Stages**:
    1.  `summarize-title`: Summarizes the imported theory.
    2.  `import-theory`: Processes and stores the theory in the database.

### `solve-verifiable-goal`
Autonomously solves a given verifiable goal or optimizes a measurable metric using a population-based evolutionary process.
- **Inputs**:
    - `goal`: A detailed description of the verifiable goal to solve.
    - `verification_instructions`: Instructions specifying how to programmatically evaluate and verify a solution candidate.
    - `max_iterations`: The maximum number of evolution iterations (default: 20).
    - `rescore_interval`: How frequently parent theories and solution candidates are rescored (default: 5).
    - `generate_intermediate_research_summaries`: Whether to generate goal progress summaries after each iteration (default: true).
- **Stages**:
    1. `summarize-title`: Summarizes the research goal.
    2. `summarize-goal-progress`: Sets up an initial overview of the goal and parameters.
    3. `initialize-theories`: Generates starter theories detailing alternative strategies for achieving the goal.
    4. `initialize-solutions`: Creates initial placeholder solution candidates.
    5. `evolve-solution-loop`: Iteratively proposes next steps, executes proposals (experiments, literature searches, or solution verifications), interprets results, integrates insights into theories, and rescores/ranks theories and solutions.

### `solve-verifiable-goal-multi-strand`
Autonomously solves a verifiable research goal by running multiple parallel research strands that compete for experiment bandwidth and periodically integrate their findings.
- **Inputs**:
    - `goal`: A detailed description of the verifiable goal to solve.
    - `verification_instructions`: Instructions specifying how to programmatically evaluate and verify a solution candidate.
    - `num_strands`: The number of parallel research strands to maintain.
    - `max_iterations`: The maximum number of iterations.
    - `integration_interval`: Iteration interval for integrating separate research strands.
- **Stages**:
    1. `summarize-title`: Summarizes the research goal.
    2. `initialize-theories`: Generates alternative starter theories.
    3. `solve-goal-loop`: Runs parallel strands that independently perform proposal-execution-interpretation-integration cycles, periodically reconciling and merging findings.

## Add-on Steps

Add-ons are individual steps that can be added to a task or run as part of a loop.

| Add-on | Description | Inputs | Applies To |
| :--- | :--- | :--- | :--- |
| `streamline-theory` | Simplifies or focuses a theory. | `theory_id`, `direction` (optional) | Theory Development |
| `review-theory` | Critically evaluates a theory. | `theory_id` | Theory Development |
| `refine-theory` | Updates a theory based on a review. | `theory_id`, `lit_review_id` (optional) | Theory Development |
| `refinement-loop` | Runs review and refinement iteratively. | `theory_id`, `max_refinements`, `apply_expansions` | Theory Development |
| `evolve-loop` | Runs a population-based evolution loop. | `evolve_iterations`, `num_parents`, `max_streamline_prob`, `write_different_prob`, `num_extra_scores`, `apply_expansions` | Theory Development |
| `polish-theory` | Improves the writing and formatting of a theory. | `theory_id` | Theory Development |
| `refine-hypothesis` | Refines a specific hypothesis within a theory. | `theory_id`, `lit_review_id` (optional) | Theory Development |
| `falsify-hypothesis` | Attempts to find evidence against a hypothesis. | `theory_id`, `hypothesis_title` | Theory Development |
| `suggest-expansions` | Suggests ways to expand the scope of a theory. | `theory_id` | Theory Development |
| `expand-theory` | Expands a theory based on suggestions. | `theory_id`, `lit_review_id` (optional) | Theory Development |
| `review-adherence` | Reviews a theory's adherence to guidance, constraints, and explanatory coverage. | `theory_id` | Theory Development |
| `improve-adherence` | Updates and refines a theory based on adherence review findings. | `theory_id`, `review_id`, `lit_review_id` (optional) | Theory Development |
| `streamline-theory-variations` | Generates multiple streamlined variations. | `theory_id` | Theory Development |
| `edit-theory` | Directly edits a theory. | `theory_id` | Both Modalities |
| `score-theories` | Assigns scores and ranks to theories. | `theory_ids` | Theory Development |
| `write-different-theory` | Writes a theory exploring a different approach than the provided previous theories. | `theory_ids`, `lit_review_id` (optional) | Theory Development |
| `summarize-research` | Summarizes the current research status. | None | Both Modalities |
| `summarize-goal-progress` | Summarizes progress towards a verifiable goal. | None | Verifiable Goals |
| `solve-goal-loop` | Runs parallel research strands to solve a verifiable goal. | `theory_ids`, `max_iterations`, `num_executions_per_iteration`, `execution_cost`, `integration_interval` | Verifiable Goals |
| `evolve-solution-loop` | Runs a population-based evolutionary loop to optimize a solution candidate. | `max_iterations`, `num_parents`, `num_extra_scores`, `rescore_interval`, `num_executions_per_iteration`, `execution_cost`, `branch_prob`, `num_proposals` | Verifiable Goals |
| `generate-solution` | Proposes and refines a new solution candidate based on active theories. | `theory_id` | Verifiable Goals |
| `score-solutions` | Scores, ranks, and compares multiple solution candidates against the goal. | `solution_ids` | Verifiable Goals |
