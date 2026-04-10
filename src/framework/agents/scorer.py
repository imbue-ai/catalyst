"""Qualitative theory scoring agent."""

from __future__ import annotations

import json
from typing import Any

from .base import LLMAgent


SYSTEM_PROMPT = """\
You are a scientific theory evaluator. You assess theories about neural network \
bifurcation on four dimensions: predictive specificity, generality, mechanistic \
depth, and falsifiability. You are rigorous and calibrated — a score of 10 is \
reserved for theories that make precise, testable predictions that have been \
confirmed. Most early theories should score 2-5."""


class QualitativeScorerAgent(LLMAgent):
    """Evaluates theory quality on multiple dimensions."""

    agent_type = "scorer"

    def __init__(self, **kwargs):
        kwargs.setdefault("system_prompt", SYSTEM_PROMPT)
        kwargs.setdefault("temperature", 0.3)
        kwargs.setdefault("max_tokens", 2048)
        super().__init__(**kwargs)

    def score_theory(
        self,
        theory_text: str,
        experiment_history: list[dict[str, Any]] | None = None,
        organism_id: str | None = None,
    ) -> dict[str, Any]:
        """Score a theory's quality.

        Returns dict with dimension scores (0-10), feedback, and overall score.
        """
        exp_summary = ""
        if experiment_history:
            parts = []
            for exp in experiment_history[-5:]:  # Last 5 experiments
                parts.append(f"- {exp.get('id', '?')}: {exp.get('interpretation', 'No interpretation')[:200]}")
            exp_summary = "\n".join(parts)

        prompt = SCORE_PROMPT.format(
            theory=theory_text,
            experiment_summary=exp_summary or "No experiments run yet.",
        )

        result = self.invoke(prompt, organism_id=organism_id)
        return result.parsed

    def _parse_response(self, raw_output: str) -> dict[str, Any]:
        import re
        match = re.search(r"```json\s*\n(.*?)```", raw_output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Fallback: try to extract scores from text
        scores = {}
        for dim in ("specificity", "generality", "mechanistic_depth", "falsifiability"):
            match = re.search(rf"{dim}.*?(\d+)", raw_output, re.IGNORECASE)
            if match:
                scores[dim] = min(10, int(match.group(1)))
        if not scores:
            scores = {"specificity": 3, "generality": 3, "mechanistic_depth": 3, "falsifiability": 3}

        return {
            "scores": scores,
            "overall": sum(scores.values()) / len(scores),
            "feedback": raw_output[:500],
            "raw": raw_output,
        }


def run_code_scorer(scorer_path: str, experiments: list[dict[str, Any]], timeout: float = 30) -> float:
    """Execute an organism's scorer.py against its experiments.

    The scorer.py must define: score(experiments: list[dict]) -> float
    Runs in a subprocess for safety.
    """
    import subprocess
    import tempfile

    runner_code = f"""
import json, sys
sys.path.insert(0, '.')
experiments = json.loads(sys.stdin.read())
# Load and run the scorer
exec(open({scorer_path!r}).read())
result = score(experiments)
print(json.dumps({{"score": float(result)}}))
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(runner_code)
        runner_path = f.name

    try:
        proc = subprocess.run(
            ["python3", runner_path],
            input=json.dumps(experiments),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            return 0.0
        result = json.loads(proc.stdout)
        return float(result["score"])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, ValueError):
        return 0.0
    finally:
        import os
        os.unlink(runner_path)


SCORE_PROMPT = """\
Evaluate the following theory about bifurcation in shallow ReLU MLPs.

## Theory
{theory}

## Experiment History
{experiment_summary}

## Scoring Dimensions

Score each dimension 0-10:

1. **Predictive Specificity** (0-10): Does the theory predict exactly WHEN \
bifurcation occurs? A score of 1 means vague ("sometimes happens"), 10 means \
precise quantitative predictions ("bifurcation occurs at width = 2 * degree(target) \
when lr < 0.05").

2. **Generality** (0-10): Does the theory cover multiple target functions and \
parameter regimes, or is it specific to one case? Higher is more general.

3. **Mechanistic Depth** (0-10): Does the theory explain WHY bifurcation occurs \
in terms of loss landscape geometry, gradient dynamics, or representation theory? \
Or does it just describe WHEN without explaining the mechanism?

4. **Falsifiability** (0-10): Could a concrete experiment disprove this theory? \
Does the theory make predictions that could be wrong? Higher means more falsifiable.

Return a JSON object:
```json
{{
    "scores": {{
        "specificity": N,
        "generality": N,
        "mechanistic_depth": N,
        "falsifiability": N
    }},
    "overall": N.N,
    "feedback": "Specific suggestions for improving this theory...",
    "strengths": ["..."],
    "weaknesses": ["..."]
}}
```"""
