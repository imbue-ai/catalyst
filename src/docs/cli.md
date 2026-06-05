# CLI Agent Usage

This document explains how to use Catalyst skills within a CLI agent (e.g., Claude Code).

This is a more manual alternative to using the Catalyst graphical user interface.

## Environment Setup

To use the skills, you must first initialize a dedicated working environment. Use the `create_environment.py` script:

```bash
uv run python create_environment.py <target_path> [--template <template_path>]
```

- `<target_path>`: The directory where the new environment will be created.
- `--template`: (Optional) Path to a template directory containing necessary scripts and tools.

This script sets up the `.claude/skills` and `.agents/skills` directories, initializes a `pyproject.toml`, and creates a `GEMINI.md` file with project-specific instructions for the agent.

Then, launch your prefered CLI agent in the environment's target directory.

## Data Ingestion

Most Catalyst skills operate on a **Theory ID**. To get existing data into the system, use the `import-theory` skill.

1.  Place your theory file (in `.tex`, `.pdf`, or `.md` format) in a location accessible to the agent.
2.  Invoke the `/import-theory` skill with the path to the file.
3.  The skill will rewrite the theory into a standard markdown format, store it in the database, and return a unique Theory ID (e.g., `T_20260512_103000_abc123`).

## Available Skills

Catalyst skills can be invoked directly by a CLI agent. They are grouped below by their primary operation mode.

### Initial Generation and Import ("Other")
These skills are typically used to start a new project or bring external data into the system.

- `/import-theory`: Imports a theory from a `.tex`, `.pdf`, or `.md` file and returns a Theory ID.
- `/support-idea`: Develops a short description or file-based idea into a full, evidenced theory.
- `/literature-review`: Performs a comprehensive literature review for a phenomenon.
- `/explore`: Performs preliminary exploration and experimentation on a phenomenon.
- `/write-theory`: Generates a single theory from scratch. Accepts a phenomenon description, and optionally a literature review ID and exploration ID.
- `/write-n-theories`: Generates multiple theories in parallel. Accepts a phenomenon description, and optionally a literature review ID and exploration ID.

### Operating on a Theory ID
These skills modify or evaluate an existing theory stored in the database. Each invocation results in a new Theory ID.

- `/edit-theory`: Applies **arbitrary** modification or research tasks to a theory based on user-provided instructions. Use this for any custom edits, deep-dives, or specific refinements not covered by other skills.
- `/streamline-theory`: Focuses or simplifies a theory's scope.
- `/review-theory`: Performs a critical evaluation and generates a review report.
- `/refine-theory`: Updates a theory based on a previous review report.
- `/polish-theory`: Improves the writing, formatting, and mathematical rigor of a theory.
- `/suggest-expansions`: Analyzes a theory and suggests ways to broaden its scope or impact.
- `/expand-theory`: Adds new sections or hypotheses to a theory based on expansion suggestions.
- `/review-adherence`: Reviews a theory's adherence to guidance, constraints, and explanatory coverage.
- `/improve-adherence`: Updates and refines a theory based on adherence review findings.
- `/streamline-theory-variations`: Generates multiple distinct simplified versions of a theory.
- `/score-theories`: Assigns scores and ranks to one or more theories based on multiple criteria.

### Operating on a Specific Hypothesis
These skills focus on a single statement (hypothesis, theorem, lemma, etc.) within a theory.

- `/falsify-hypothesis`: Attempts to find logical or empirical evidence against a specific hypothesis within a theory.
- `/refine-hypothesis`: Improves a specific hypothesis based on one or more falsification reports.

## Context Management

The `context_manager.py` script is the core of Catalyst's data persistence. It manages the `.ai-scientist-db` directory.

All Catalyst skills will internally utilize the context manager to retrieve context (such as an existing theory), and store their results. The context database is immutable: Once a result has been stored, it cannot be changed. This means that each change that a Catalyst skill makes to a theory will result in a brand new theory ID.

- **Storage**: Skills use `context_manager.py store_results` to save their outputs (theories, reviews, experiments, etc.) into the database.
- **Context Assembly**: Skills use `context_manager.py create_context` to assemble required artifacts from the database into the agent's current working folder.
- **Listing and Searching**: Use `context_manager.py list` to view stored entries and `context_manager.py search_experiments` to find prior experiments.

## Outputs and Database Structure

All results are stored in the `.ai-scientist-db` directory:

- `exploration/`: Reports from the `explore` skill.
- `literature/`: Summaries from `literature-review`.
- `theory/`: Markdown theory files (`theory.md`) and associated artifacts.
- `review/`: Critical evaluations and falsification reports.
- `experiment/`: Descriptions and results of experiments.
- `prediction/`: Predicted outcomes of experiments.

Each entry is stored in a subdirectory named after its unique ID and contains a markdown file and a `metadata.json` file.
