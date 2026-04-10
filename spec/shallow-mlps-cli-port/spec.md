# AI Scientist: Theory Evolution Framework for Shallow MLP Bifurcation

## Overview

This system is an AI-driven scientific investigation framework, initially targeting the bifurcation phenomenon in shallow (two-layer) ReLU MLPs. When a shallow MLP is trained to approximate a target function, its learned features can undergo sudden qualitative transitions—bifurcations—as continuous parameters (network width, learning rate, target function shape) are varied. The interactive demo at jamiesimon.io/shallow-mlps visualizes this: individual ReLU neurons' contributions are plotted as colored lines, and at certain parameter thresholds the network abruptly reorganizes from one representational strategy to another.

The system has three layers. First, a **Python CLI port** of the shallow-mlps experiment replaces the browser-based JavaScript demo, producing JSON data, PNG plots, and text summaries that agents can consume programmatically. Second, a **coordinator harness** written in Python manages a population of "theory organisms," each representing a hypothesis about when and why bifurcation occurs. Third, **specialized subagents** (invoked via the Claude Code CLI or the Anthropic SDK) perform tasks like running experiments, interpreting results, scoring theories, and mutating organisms to produce new hypotheses.

A researcher using this system would: (1) initialize a seed organism with an initial theory about bifurcation, (2) launch the coordinator, which autonomously runs experiment loops—proposing experiments, executing the CLI tool, interpreting results, scoring theories, and mutating organisms—and (3) inspect the evolving population of theories, their scores, and the experiment artifacts that support or refute them. All inputs and outputs for every subagent invocation are logged to disk, enabling replay and isolated testing of any component.

The architecture is designed to be domain-agnostic: the shallow-mlps CLI and bifurcation-specific prompts are plugged into a general-purpose theory evolution framework that can later be retargeted to other scientific phenomena.

## Summary

The system operates through three main data flows:

**Experiment execution flow.** The coordinator selects an organism and asks an experiment-designer subagent to propose an experiment (a set of CLI parameters) that would test the organism's theory. The coordinator invokes the shallow-mlps CLI with those parameters. The CLI trains one or more shallow MLPs using PyTorch, sweeping over a parameter range, and writes outputs: a JSON file with per-neuron weights, loss curves, and learned function samples; PNG plots showing individual neuron contributions and the aggregate learned function at each parameter value; and a text summary describing what happened. An experiment-interpreter subagent then reads these artifacts and produces a structured analysis: what was observed, whether bifurcation occurred, and how the results relate to the theory being tested.

**Scoring flow.** Each organism contains a `scorer.py` that implements a code-based scoring function. When new experiment results arrive, the coordinator runs the scorer against all accumulated experiment results for that organism, producing a numeric score. A separate LLM-based "qualitative scorer" subagent evaluates the theory's prose quality—specificity, falsifiability, mechanistic depth—and provides improvement feedback. The combined score determines the organism's fitness.

**Mutation flow.** The coordinator selects high-scoring organisms and invokes a mutation subagent, which receives the parent organism's theory, its experiment history, and its scores. The subagent produces a new organism with a modified theory (and potentially a modified scorer) that addresses weaknesses identified by the scoring flow. All mutation is currently LLM-driven; structured mutation operators (e.g., parameter perturbation, theory merging) can be added later as patterns emerge. Each new organism is written to its own directory with full provenance metadata linking it to its parent.

**Logging and replay.** Every subagent invocation is logged as a self-contained "invocation record" containing: the agent type, the full prompt, all file inputs (snapshotted), and the complete output. These records enable replaying any component in isolation for debugging or regression testing.

## Implementation Plan

The project lives in `/Users/catherinekim/ai-scientist/` with the following structure:

### Directory Layout

```
ai-scientist/
├── shallow_mlps/           # Python CLI port of the experiment
│   ├── __init__.py
│   ├── cli.py              # CLI entry point (argparse)
│   ├── train.py            # MLP training logic
│   ├── targets.py          # Target function definitions and parsing
│   ├── plot.py             # Matplotlib plotting utilities
│   └── analyze.py          # Bifurcation detection heuristics
├── framework/              # Domain-agnostic theory evolution framework
│   ├── __init__.py
│   ├── coordinator.py      # Main orchestration loop
│   ├── organism.py         # Organism data model and filesystem operations
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py         # Base agent class with logging/replay
│   │   ├── experimenter.py # Experiment design subagent
│   │   ├── interpreter.py  # Experiment result interpretation subagent
│   │   ├── scorer.py       # Qualitative theory scoring subagent
│   │   ├── mutator.py      # Theory mutation subagent
│   │   └── verifier.py     # Bifurcation verification subagent
│   ├── logging.py          # Invocation record logging and replay
│   ├── config.py           # Framework configuration
│   └── prompts/            # Prompt templates (stored as text files)
│       ├── experimenter.md
│       ├── interpreter.md
│       ├── scorer.md
│       ├── mutator.md
│       └── verifier.md
├── organisms/              # Living population of theory organisms
│   └── seed_001/           # Example organism directory
│       ├── theory.md
│       ├── scorer.py
│       ├── metadata.json
│       └── experiments/
│           └── exp_001/
│               ├── params.json
│               ├── results.json
│               ├── plots/
│               ├── interpretation.md
│               └── invocation_log.json
├── logs/                   # Global invocation logs for replay
├── pyproject.toml
└── README.md
```

### `shallow_mlps/` — Python CLI Port

**`shallow_mlps/train.py`**: Core training module.
- `ShallowMLP(nn.Module)`: A two-layer ReLU network with configurable input dimension (1 or 2), hidden width, and output dimension 1. Exposes per-neuron decomposition: for a 1-hidden-layer ReLU net, the output is a sum of scaled ReLU functions, each defined by a weight vector and bias. Methods: `forward(x)`, `get_neuron_contributions(x)` (returns per-neuron output over input grid), `get_weights_snapshot()` (returns serializable dict of all parameters).
- `train_mlp(target_fn, width, lr, steps, input_dim, weight_decay, seed)` → `TrainResult`: Trains a single MLP instance. Returns a `TrainResult` dataclass containing: final model, loss curve, per-neuron contributions evaluated on a grid, and the final learned function evaluated on a grid.
- `sweep_parameter(target_fn, param_name, param_values, fixed_params, seeds)` → `SweepResult`: Trains multiple MLPs across a parameter sweep (e.g., varying width from 2 to 64). For each parameter value, trains `len(seeds)` replicates. Returns a `SweepResult` with all `TrainResult` objects organized by parameter value and seed.

**`shallow_mlps/targets.py`**: Target function definitions.
- `parse_target(spec_string)` → callable: Parses a target function specification. Supports named presets (e.g., `"abs"`, `"step"`, `"sine"`) and custom expressions using a safe eval with numpy functions. The custom expression format matches the demo: `"sin(x[1]) + x[1] + x[2] - .2 * sin(x[1] + x[2])"` where `x[1]`, `x[2]` are input dimensions (1-indexed to match the demo's convention).
- `PRESET_TARGETS`: Dict mapping names to `(callable, description)` tuples. Includes targets known to exhibit bifurcation and ones that don't, for calibration.

**`shallow_mlps/plot.py`**: Visualization.
- `plot_neuron_contributions(train_result, ax=None)` → matplotlib figure: Plots individual neuron contributions as colored lines (matching the demo's visual style), plus the aggregate learned function and target function.
- `plot_sweep(sweep_result, output_dir)`: Generates a grid of neuron-contribution plots across the parameter sweep, plus a summary plot showing how the "representational structure" changes. Saves PNGs to `output_dir`.
- `plot_loss_curves(sweep_result, output_dir)`: Loss curves across the sweep.

**`shallow_mlps/analyze.py`**: Programmatic bifurcation detection.
- `detect_bifurcation(sweep_result, method="weight_discontinuity")` → `BifurcationReport`: Analyzes a parameter sweep for bifurcation events. Returns a dataclass listing detected bifurcation points (parameter values where abrupt transitions occur), the magnitude of each transition, and a confidence score. Methods: `"weight_discontinuity"` (detects sudden jumps in weight-space distance between consecutive parameter values), `"representation_clustering"` (clusters the learned representations and detects where cluster identity changes), `"loss_landscape"` (detects where loss curve character changes abruptly).
- `BifurcationReport`: Dataclass with fields `bifurcation_points: list[dict]` (each with `param_value`, `magnitude`, `confidence`, `description`), `overall_detected: bool`, `summary: str`.

**`shallow_mlps/cli.py`**: Command-line interface.
- Subcommands: `train` (single training run), `sweep` (parameter sweep), `analyze` (run bifurcation detection on saved sweep results), `list-targets` (show available preset targets).
- `train` flags: `--target`, `--width`, `--lr`, `--steps`, `--input-dim`, `--seed`, `--output-dir`.
- `sweep` flags: `--target`, `--sweep-param`, `--sweep-range` (e.g., `2,4,8,16,32,64`), `--seeds` (number of replicates), `--output-dir`, plus fixed params for non-swept parameters.
- All subcommands write: `results.json` (full numeric data), `summary.txt` (human-readable text summary), and PNG plots to the output directory. The `sweep` command additionally writes `bifurcation_report.json` from the automatic detector.

### `framework/` — Theory Evolution Framework

**`framework/organism.py`**: Organism data model.
- `Organism`: Dataclass representing a theory organism. Fields: `id: str`, `parent_id: Optional[str]`, `theory_path: Path` (path to `theory.md`), `scorer_path: Path` (path to `scorer.py`), `metadata: dict` (creation time, generation number, lineage), `experiments: list[ExperimentRecord]`, `scores: dict` (latest qualitative and quantitative scores).
- `load_organism(directory: Path)` → `Organism`: Loads an organism from its directory.
- `create_organism(parent: Optional[Organism], theory_text: str, scorer_code: str, organisms_dir: Path)` → `Organism`: Creates a new organism directory with all required files and metadata, linking to parent if provided.
- `ExperimentRecord`: Dataclass with `id`, `params`, `results_path`, `interpretation`, `timestamp`.

**`framework/agents/base.py`**: Base agent infrastructure.
- `AgentBase`: Abstract base class. Handles invocation logging (captures prompt, file inputs, outputs to an invocation record), manages timeouts, and provides `invoke(prompt: str, file_context: dict[str, str])` → `AgentResult`. Subclasses override `_build_prompt()` and `_parse_response()`.
- `LLMAgent(AgentBase)`: Agent that makes a direct Anthropic SDK API call. Used for tasks that don't need file/shell tools (interpretation, scoring, mutation).
- `CLIAgent(AgentBase)`: Agent that invokes `claude` CLI as a subprocess, giving the subagent access to file reading, shell execution, etc. Used for experiment design and verification where the agent may need to inspect prior results.
- `AgentResult`: Dataclass with `raw_output: str`, `parsed: Any`, `invocation_id: str`, `duration_seconds: float`.

**`framework/agents/experimenter.py`**: Experiment design agent.
- `ExperimenterAgent(CLIAgent)`: Given an organism's theory and prior experiment results, proposes a new experiment as a JSON specification of CLI parameters. The prompt instructs the agent to design experiments that would either support or falsify the theory, prioritizing experiments at predicted bifurcation boundaries.

**`framework/agents/interpreter.py`**: Result interpretation agent.
- `InterpreterAgent(LLMAgent)`: Given experiment parameters, the JSON results, plot image paths, and the theory being tested, produces a structured interpretation: observations, whether bifurcation was detected, how results relate to the theory, and suggested follow-up experiments.

**`framework/agents/scorer.py`**: Qualitative theory scorer.
- `QualitativeScorerAgent(LLMAgent)`: Evaluates a theory on dimensions: predictive specificity (does it predict exactly when bifurcation occurs?), generality (does it cover multiple target functions and parameter regimes?), mechanistic depth (does it explain *why*?), falsifiability (could an experiment disprove it?). Returns a structured score (0–10 per dimension) and prose feedback on how to improve.

**`framework/agents/mutator.py`**: Theory mutation agent.
- `MutatorAgent(LLMAgent)`: Given a parent organism (theory, scores, experiment history, qualitative feedback), produces a mutated theory and optionally a modified scorer. Mutation strategies include: addressing specific weaknesses flagged by the scorer, incorporating new experimental evidence, generalizing or specializing the theory, and proposing novel mechanisms. The agent outputs the full text of the new `theory.md` and `scorer.py`.

**`framework/agents/verifier.py`**: Bifurcation verification agent.
- `VerifierAgent(CLIAgent)`: A specialized agent that takes experiment outputs and independently determines whether bifurcation occurred. Can run additional analysis scripts if needed. Used as a second opinion to validate the automated detector and the interpreter's claims.

**`framework/logging.py`**: Invocation logging and replay.
- `InvocationRecord`: Dataclass with `id`, `agent_type`, `timestamp`, `prompt`, `file_inputs` (dict of filename→content snapshots), `output`, `duration_seconds`, `organism_id`, `experiment_id`.
- `log_invocation(record: InvocationRecord, log_dir: Path)`: Writes record as JSON to `log_dir/{id}.json`. File input snapshots are stored inline for small files, or as references for large ones (plots).
- `replay_invocation(record_path: Path, agent: AgentBase)` → `AgentResult`: Re-runs an agent with the exact same inputs from a saved record, for debugging and regression testing.
- `list_invocations(log_dir: Path, filters: dict)` → `list[InvocationRecord]`: Query logged invocations by agent type, organism, time range, etc.

**`framework/coordinator.py`**: Main orchestration loop.
- `Coordinator`: The outer harness that drives the theory evolution cycle. Configured via a YAML or JSON config file specifying: the phenomenon description file, max generations, population size, mutation rate, selection strategy, experiment budget per organism, and agent model settings.
- `Coordinator.run(generations: int)`: Main loop. For each generation: (1) select organisms for experimentation based on scores and exploration/exploitation balance, (2) for each selected organism, invoke the experimenter to design an experiment, (3) run the experiment via the shallow-mlps CLI, (4) invoke the interpreter on results, (5) update scores by running the organism's `scorer.py` on all its experiments plus the qualitative scorer, (6) select organisms for mutation, (7) invoke the mutator to produce child organisms, (8) prune low-scoring organisms if population exceeds limit.
- `Coordinator.run_single_experiment(organism_id: str)`: Run one experiment cycle for a specific organism (useful for debugging).
- `Coordinator.rescore_all()`: Re-run all code-based scorers on all experiments (useful after scorer updates).

**`framework/config.py`**: Configuration management.
- `FrameworkConfig`: Pydantic model for the config file. Fields: `phenomenon_description_path`, `organisms_dir`, `logs_dir`, `max_population`, `generations`, `experiments_per_organism_per_generation`, `selection_strategy` (tournament, top-k, etc.), `agent_configs` (per-agent-type model and temperature settings), `cli_tool_path` (path to shallow-mlps CLI).

**`framework/prompts/`**: Prompt templates stored as markdown files. Each template uses `{placeholder}` syntax for variable substitution. Keeping prompts as files (rather than inline strings) makes them easy to iterate on and version-control.

### Configuration and Entry Points

**`pyproject.toml`**: Project metadata, dependencies (torch, matplotlib, numpy, anthropic, pyyaml, pydantic), and script entry points: `shallow-mlps` → `shallow_mlps.cli:main`, `ai-scientist` → `framework.coordinator:main`.

### Organism Directory Structure (per organism)

Each organism directory contains:
- `theory.md`: The theory in prose, with explicit predictions about when bifurcation occurs and why.
- `scorer.py`: A Python script that defines a `score(experiments: list[dict]) -> float` function. The scorer receives a list of experiment result dicts and returns a numeric score reflecting how well the theory's predictions matched observations.
- `metadata.json`: `{id, parent_id, generation, created_at, lineage: [ancestor_ids]}`.
- `experiments/exp_NNN/`: Each experiment subdirectory contains `params.json`, `results.json`, `plots/*.png`, `interpretation.md`, `bifurcation_report.json`, and `invocation_log.json`.

## Implementation Phases

### Phase 1: Python CLI Port and Manual Experimentation

Build the `shallow_mlps/` package end to end. This means implementing `train.py` with the `ShallowMLP` model and training loop, `targets.py` with preset targets and custom expression parsing, `plot.py` with neuron-contribution visualizations matching the style of the original demo, `analyze.py` with at least the weight-discontinuity bifurcation detector, and `cli.py` tying it all together. The deliverable is a working CLI where a user (or agent) can run `shallow-mlps sweep --target "abs(x)" --sweep-param width --sweep-range 2,4,8,16,32,64 --output-dir ./results` and get JSON data, PNG plots, and a text summary. Validate by reproducing the bifurcation phenomenon shown in the original demo with the user's example target function.

### Phase 2: Single-Agent Experiment Loop

Build the minimal agent infrastructure: `base.py` with `LLMAgent` (Anthropic SDK calls), the invocation logging system in `logging.py`, and the `InterpreterAgent` and `VerifierAgent`. Wire up a simple script (not yet the full coordinator) that: (1) runs a sweep with known-good parameters, (2) asks the interpreter agent to analyze the results, (3) asks the verifier agent to confirm whether bifurcation was detected, and (4) logs all invocations. This validates that agents can consume the CLI's outputs and reason about bifurcation. Also implement the experiment where the agent tunes a single numeric parameter to find the range that produces bifurcation, matching step 2.3 from the requirements.

### Phase 3: Organism Data Model and Scoring

Implement `organism.py` with the full data model and filesystem operations, the code-based scorer infrastructure (loading and executing `scorer.py` from organism directories), and the `QualitativeScorerAgent`. Create the seed organism manually: write an initial `theory.md` with a basic hypothesis about bifurcation (e.g., "bifurcation occurs when the network width crosses a threshold relative to the complexity of the target function"), a simple `scorer.py`, and run several experiments against it. Validate that the scoring pipeline produces meaningful differentiation between good and bad theories.

### Phase 4: Mutation and Evolution Loop

Implement `MutatorAgent`, the `CLIAgent` base class (for agents that need shell access via the Claude Code CLI), the `ExperimenterAgent`, and the full `Coordinator` with its generation loop. Create the config system and the `ai-scientist` entry point. Run the first multi-generation evolution: start with the seed organism, let the coordinator run 3–5 generations of experiment → score → mutate, and inspect the resulting population of theories. Validate that theories are improving (scores increase, predictions become more specific) and that the logging system captures everything needed for replay.

### Phase 5: Replay, Robustness, and Extensibility

Implement `replay_invocation` and build a small replay CLI (`ai-scientist replay <invocation-id>`) for debugging. Add the `CLIAgent`-based experimenter that can inspect prior results when designing new experiments. Implement population management (pruning, selection strategies). Harden error handling throughout: agent timeouts, malformed outputs, failed training runs. Write integration tests that replay logged invocations and verify deterministic outputs. Document the extension points for targeting new phenomena: what needs to change (target CLI tool, prompt templates, seed organism) and what stays the same (coordinator, agent infrastructure, logging).

## Open Questions

**Scorer code safety.** Each organism's `scorer.py` is generated by an LLM and executed. What sandboxing is needed? Options range from subprocess isolation with resource limits to a restricted Python subset. For Phase 1–3 we can rely on subprocess execution with timeouts, but this needs a more robust solution before running at scale.

**Theory structure format.** The spec calls for `theory.md` as free-form prose, but the scoring and mutation agents would benefit from a more structured format (e.g., explicit "predictions" and "mechanisms" sections). Should we define a template for `theory.md` upfront, or let the structure emerge and standardize later?

**2D target functions.** The original demo supports 2D input functions (the user's example uses `x[1]` and `x[2]`). The CLI port should support both 1D and 2D inputs, but 2D visualization is significantly more complex (surface plots or heatmaps vs. line plots). Should Phase 1 support 2D, or defer it?

**Shared vs. organism-local experiment results.** Two organisms might predict different things about the same experiment. Should experiment results be stored globally and referenced by organisms, or duplicated per-organism? Global storage saves compute (no re-running identical experiments) but complicates the organism-as-self-contained-directory model.

**Agent model selection.** Different agent roles have different cost/quality tradeoffs. The interpreter and mutator likely need a strong model (Claude Opus or Sonnet), while the verifier might work with a smaller model. Should the config specify per-agent-type model choices, and what are reasonable defaults?

**Coordinator determinism and concurrency.** Should the coordinator support running multiple experiment loops in parallel (e.g., experimenting on several organisms simultaneously)? This would speed up evolution but complicates logging and resource management. Starting single-threaded is simpler, but the design should not preclude later parallelism.

**Knowledge seeker reuse.** The user's `~/knowledge_seeker` project contains mutation logic that should inform this implementation, but it was not accessible during spec writing. Before Phase 4 implementation, the mutation patterns from that codebase should be reviewed and adapted. Specifically: how did it structure mutation prompts, what mutation operators existed, and how did it handle lineage tracking?
