"""Theory mutation agent — produces evolved versions of theories."""

from __future__ import annotations

import json
from typing import Any

from .base import LLMAgent


SYSTEM_PROMPT = """\
You are a scientific theory mutator. Given a parent theory about bifurcation in \
shallow ReLU MLPs, its experimental evidence, and scoring feedback, you produce \
an improved child theory. Your mutations should be substantive — not just \
rewording, but genuinely new insights, mechanisms, or predictions.

Mutation strategies you can employ:
1. Address specific weaknesses identified by the scorer
2. Incorporate new experimental evidence
3. Generalize the theory to cover more cases
4. Specialize with more precise quantitative predictions
5. Propose novel mechanisms (loss landscape geometry, symmetry breaking, etc.)
6. Merge insights from multiple experiments"""


class MutatorAgent(LLMAgent):
    """Produces mutated versions of theories."""

    agent_type = "mutator"

    def __init__(self, **kwargs):
        kwargs.setdefault("system_prompt", SYSTEM_PROMPT)
        kwargs.setdefault("temperature", 0.9)
        kwargs.setdefault("max_tokens", 8192)
        super().__init__(**kwargs)

    def mutate(
        self,
        theory_text: str,
        scorer_code: str,
        experiment_history: list[dict[str, Any]] | None = None,
        scores: dict[str, Any] | None = None,
        qualitative_feedback: str = "",
        organism_id: str | None = None,
    ) -> dict[str, Any]:
        """Produce a mutated theory and scorer.

        Returns dict with: theory (str), scorer (str), mutation_description (str).
        """
        exp_summary = ""
        if experiment_history:
            parts = []
            for exp in experiment_history[-5:]:
                parts.append(
                    f"- {exp.get('id', '?')}: {exp.get('interpretation', 'N/A')[:300]}"
                )
            exp_summary = "\n".join(parts)

        prompt = MUTATE_PROMPT.format(
            theory=theory_text,
            scorer=scorer_code,
            experiment_summary=exp_summary or "No experiments yet.",
            scores=json.dumps(scores, indent=2) if scores else "No scores yet.",
            feedback=qualitative_feedback or "No feedback yet.",
        )

        result = self.invoke(prompt, organism_id=organism_id)
        return result.parsed

    def _parse_response(self, raw_output: str) -> dict[str, Any]:
        import re

        # Extract theory from markdown block
        theory_match = re.search(
            r"## (?:New |Mutated )?Theory\s*\n(.*?)(?=\n## |\n```python\b|\Z)",
            raw_output, re.DOTALL | re.IGNORECASE
        )
        theory = theory_match.group(1).strip() if theory_match else ""

        # Extract scorer code
        scorer_match = re.search(
            r"```python\s*\n(.*?)```",
            raw_output, re.DOTALL
        )
        scorer = scorer_match.group(1).strip() if scorer_match else ""

        # Extract mutation description
        desc_match = re.search(
            r"## (?:Mutation )?Description\s*\n(.*?)(?=\n## |\Z)",
            raw_output, re.DOTALL | re.IGNORECASE
        )
        description = desc_match.group(1).strip() if desc_match else ""

        # If no structured extraction worked, use the whole output as theory
        if not theory:
            theory = raw_output

        # Provide a default scorer if none was generated
        if not scorer or "def score" not in scorer:
            scorer = DEFAULT_SCORER

        return {
            "theory": theory,
            "scorer": scorer,
            "mutation_description": description,
            "raw": raw_output,
        }


DEFAULT_SCORER = '''\
def score(experiments: list[dict]) -> float:
    """Score how well experiments match theory predictions."""
    if not experiments:
        return 0.0

    total = 0.0
    for exp in experiments:
        # Basic scoring: reward low loss and bifurcation detection
        report = exp.get("bifurcation_report", {})
        if report.get("overall_detected"):
            total += 5.0
        loss = exp.get("final_loss", 1.0)
        total += max(0, 5.0 - loss * 10)

    return total / len(experiments)
'''


MUTATE_PROMPT = """\
You are evolving a scientific theory about bifurcation in shallow ReLU MLPs.

## Parent Theory
{theory}

## Current Scorer Code
```python
{scorer}
```

## Experiment History
{experiment_summary}

## Current Scores
{scores}

## Qualitative Feedback
{feedback}

## Instructions

Produce an IMPROVED child theory that addresses the weaknesses identified above. \
Your mutation should be substantive — not just rewording.

Structure your response EXACTLY as follows:

## New Theory

[Write the complete new theory here. Include explicit predictions about when \
bifurcation occurs, proposed mechanisms, and testable hypotheses.]

## Mutation Description

[Describe what changed and why.]

## Scorer

```python
def score(experiments: list[dict]) -> float:
    \"\"\"Score how well experiments match this theory's predictions.

    Each experiment dict has keys: params, final_loss, bifurcation_report, \
    neuron_contributions, learned_fn, target_fn_values, width, lr, steps.
    The bifurcation_report has: overall_detected, bifurcation_points, summary.
    \"\"\"
    if not experiments:
        return 0.0

    # Implement scoring logic that tests THIS theory's specific predictions
    total = 0.0
    for exp in experiments:
        # Score each experiment...
        pass
    return total / len(experiments)
```

The scorer must be a standalone Python function using only builtins and basic math. \
It receives experiment result dicts and returns a float score (higher = better match)."""
