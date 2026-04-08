"""Theory refinement agent — salvages dismissed theories.

Directly inspired by knowledge_seeker's refiner.py: when a theory is dismissed
(confidence drops below threshold), the refiner attempts to salvage it by
proposing a generalized or modified variant, rather than simply discarding it.
"""

from __future__ import annotations

import json
from typing import Any

from .base import LLMAgent


SYSTEM_PROMPT = """\
You are a scientific theory refiner. When a theory about bifurcation in shallow \
ReLU MLPs has been dismissed (disproven or poorly supported by experiments), \
you attempt to salvage its core insights by proposing a refined, generalized, \
or corrected variant.

Your refinements should be substantive — not just weakening the original claim, \
but identifying what kernel of truth might exist and expressing it more precisely. \
Sometimes the right refinement is a completely different framing of the same \
underlying observation."""


class RefinerAgent(LLMAgent):
    """Attempts to salvage dismissed theories by refinement.

    Knowledge_seeker pattern: dismissed hypotheses aren't deleted — the refiner
    samples them and proposes generalized variants. The refined theory inherits
    the parent's evidence history, enabling learning from past failures.
    """

    agent_type = "refiner"

    def __init__(self, **kwargs):
        kwargs.setdefault("system_prompt", SYSTEM_PROMPT)
        kwargs.setdefault("temperature", 0.7)
        kwargs.setdefault("max_tokens", 4096)
        super().__init__(**kwargs)

    def refine(
        self,
        dismissed_theory: str,
        evidence_history: list[dict[str, Any]],
        experiment_summaries: list[str],
        organism_id: str | None = None,
    ) -> dict[str, Any]:
        """Attempt to refine a dismissed theory.

        Returns dict with:
            refined_theory: str | None — the new theory text, or None if unsalvageable
            confidence: float — how confident the refiner is in the refinement
            scorer: str — updated scorer code
            reasoning: str — why this refinement was chosen
        """
        evidence_text = ""
        if evidence_history:
            parts = []
            for ev in evidence_history[-6:]:
                delta = ev.get("confidence_delta", 0)
                direction = "supporting" if delta > 0 else "contradicting"
                parts.append(
                    f"- [{direction}, delta={delta:+.2f}] {ev.get('explanation', 'N/A')}"
                )
            evidence_text = "\n".join(parts)

        exp_text = "\n".join(
            f"- {s[:300]}" for s in experiment_summaries[-4:]
        ) if experiment_summaries else "No experiment summaries available."

        prompt = REFINE_PROMPT.format(
            dismissed_theory=dismissed_theory,
            evidence_history=evidence_text or "No evidence recorded.",
            experiment_summaries=exp_text,
        )

        result = self.invoke(prompt, organism_id=organism_id)
        return result.parsed

    def _parse_response(self, raw_output: str) -> dict[str, Any]:
        import re

        # Try JSON extraction
        match = re.search(r"```json\s*\n(.*?)```", raw_output, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                return data
            except json.JSONDecodeError:
                pass

        # Extract theory section
        theory_match = re.search(
            r"## (?:Refined )?Theory\s*\n(.*?)(?=\n## |\n```python\b|\Z)",
            raw_output, re.DOTALL | re.IGNORECASE,
        )
        theory = theory_match.group(1).strip() if theory_match else None

        # Extract scorer
        scorer_match = re.search(r"```python\s*\n(.*?)```", raw_output, re.DOTALL)
        scorer = scorer_match.group(1).strip() if scorer_match else ""

        # Extract confidence
        conf_match = re.search(r"confidence[:\s]+([0-9.]+)", raw_output, re.IGNORECASE)
        confidence = float(conf_match.group(1)) if conf_match else 0.3

        return {
            "refined_theory": theory,
            "confidence": confidence,
            "scorer": scorer,
            "reasoning": raw_output[:500],
        }


REFINE_PROMPT = """\
A theory about bifurcation in shallow ReLU MLPs has been dismissed after \
experiments failed to support it. Attempt to salvage its core insights.

## Dismissed Theory
{dismissed_theory}

## Evidence History (most recent)
{evidence_history}

## Experiment Summaries
{experiment_summaries}

## Instructions

Analyze WHY this theory was dismissed. Then either:

1. **Refine it**: Propose a modified version that accounts for the contradicting \
evidence. Perhaps the original claim was too strong, too specific, or applied \
only to a subset of cases.

2. **Reframe it**: The core observation might be correct but the explanation \
wrong. Propose a different mechanism for the same observations.

3. **Declare unsalvageable**: If there's genuinely nothing to save, say so.

Structure your response:

## Refined Theory
[Complete new theory text, or "UNSALVAGEABLE" if nothing to save]

## Reasoning
[Why this refinement addresses the evidence against the original]

## Scorer
```python
def score(experiments: list[dict]) -> float:
    # Scoring logic for the refined theory
    ...
```

Also provide a confidence estimate (0.0-1.0) for how well this refined theory \
is likely to hold up: confidence: X.X"""
