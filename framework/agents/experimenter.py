"""Experiment design agent — proposes experiments to test theories."""

from __future__ import annotations

import json
from typing import Any

from .base import LLMAgent


SYSTEM_PROMPT = """\
You are an experiment designer for investigating bifurcation in shallow ReLU \
MLPs. You design experiments (CLI parameter configurations) that would test \
or falsify a given theory. You prioritize experiments at predicted bifurcation \
boundaries — parameter values where the theory predicts transitions should occur.

The CLI tool supports:
- `sweep` command with: --target, --sweep-param (width|lr|steps), \
--sweep-range (comma-separated values), --seeds, --width, --lr, --steps, \
--input-dim, --weight-decay, --output-dir
- Preset targets: abs, step, sine, quadratic, sawtooth, relu, hat
- Custom targets: any numpy expression using x, x[1], x[2]"""


class ExperimenterAgent(LLMAgent):
    """Designs experiments to test organism theories."""

    agent_type = "experimenter"

    def __init__(self, **kwargs):
        kwargs.setdefault("system_prompt", SYSTEM_PROMPT)
        kwargs.setdefault("temperature", 0.7)
        super().__init__(**kwargs)

    def design_experiment(
        self,
        theory_text: str,
        prior_experiments: list[dict[str, Any]] | None = None,
        organism_id: str | None = None,
    ) -> dict[str, Any]:
        """Propose an experiment to test a theory.

        Returns a dict with CLI parameters for the experiment.
        """
        prior_summary = ""
        if prior_experiments:
            parts = []
            for exp in prior_experiments[-5:]:
                parts.append(
                    f"- Params: {json.dumps(exp.get('params', {}))}\n"
                    f"  Result: {exp.get('interpretation', 'N/A')[:200]}"
                )
            prior_summary = "\n".join(parts)

        prompt = DESIGN_PROMPT.format(
            theory=theory_text,
            prior_experiments=prior_summary or "No prior experiments.",
        )

        result = self.invoke(prompt, organism_id=organism_id)
        return result.parsed

    def _parse_response(self, raw_output: str) -> dict[str, Any]:
        import re
        match = re.search(r"```json\s*\n(.*?)```", raw_output, re.DOTALL)
        if match:
            try:
                params = json.loads(match.group(1))
                return _validate_experiment_params(params)
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback: return a default experiment
        return {
            "command": "sweep",
            "target": "abs",
            "sweep_param": "width",
            "sweep_range": "2,4,8,16,32",
            "seeds": 3,
            "steps": 5000,
            "lr": 0.01,
            "rationale": f"Fallback experiment (could not parse agent output). Raw: {raw_output[:200]}",
        }


def _validate_experiment_params(params: dict[str, Any]) -> dict[str, Any]:
    """Validate and sanitize experiment parameters."""
    defaults = {
        "command": "sweep",
        "target": "abs",
        "sweep_param": "width",
        "sweep_range": "2,4,8,16,32",
        "seeds": 1,
        "steps": 5000,
        "lr": 0.01,
        "width": 16,
        "input_dim": 1,
        "weight_decay": 0.0,
    }

    validated = {**defaults}
    for key in defaults:
        if key in params:
            validated[key] = params[key]

    # Copy rationale if present
    if "rationale" in params:
        validated["rationale"] = params["rationale"]

    # Ensure sweep_param is valid
    if validated["sweep_param"] not in ("width", "lr", "steps"):
        validated["sweep_param"] = "width"

    # Cap training steps to avoid excessive compute
    if isinstance(validated["steps"], (int, float)):
        validated["steps"] = min(int(validated["steps"]), 20000)

    # Cap seeds
    if isinstance(validated["seeds"], (int, float)):
        validated["seeds"] = min(int(validated["seeds"]), 5)

    return validated


DESIGN_PROMPT = """\
Design an experiment to test the following theory about bifurcation in shallow \
ReLU MLPs.

## Theory
{theory}

## Prior Experiments
{prior_experiments}

## Instructions

Design ONE experiment that would best test this theory. Prioritize:
1. Experiments at predicted bifurcation boundaries
2. Experiments that could falsify the theory
3. Experiments that explore untested parameter regimes
4. Experiments that use different target functions than prior ones

Return a JSON object with CLI parameters:
```json
{{
    "command": "sweep",
    "target": "abs",
    "sweep_param": "width",
    "sweep_range": "2,4,8,16,32,64",
    "seeds": 3,
    "steps": 5000,
    "lr": 0.01,
    "width": 16,
    "input_dim": 1,
    "weight_decay": 0.0,
    "rationale": "Why this experiment tests the theory..."
}}
```

The target can be a preset name (abs, step, sine, quadratic, sawtooth, relu, hat) \
or a custom numpy expression like "abs(x) + 0.5*sin(3*x)".

The sweep_param must be one of: width, lr, steps.
The sweep_range is comma-separated values for the swept parameter."""
