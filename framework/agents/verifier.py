"""Bifurcation verification agent — independent second opinion."""

from __future__ import annotations

import json
from typing import Any

from .base import LLMAgent


SYSTEM_PROMPT = """\
You are a bifurcation verification specialist. Your job is to independently \
determine whether bifurcation occurred in shallow MLP training experiments, \
without being influenced by prior claims. You examine the raw data carefully \
and make your own determination.

Bifurcation means a sudden qualitative reorganization of the network's \
representational strategy — not just gradual improvement with more capacity."""


class VerifierAgent(LLMAgent):
    """Independently verifies whether bifurcation occurred."""

    agent_type = "verifier"

    def __init__(self, **kwargs):
        kwargs.setdefault("system_prompt", SYSTEM_PROMPT)
        kwargs.setdefault("temperature", 0.2)
        super().__init__(**kwargs)

    def verify(
        self,
        results_data: dict[str, Any],
        bifurcation_report: dict[str, Any] | None = None,
        interpreter_claim: bool | None = None,
        organism_id: str | None = None,
        experiment_id: str | None = None,
    ) -> dict[str, Any]:
        """Independently verify bifurcation claims.

        Returns dict with: verified, confidence, reasoning, details.
        """
        prompt = VERIFY_PROMPT.format(
            results_summary=_summarize_for_verification(results_data),
            auto_report=json.dumps(bifurcation_report, indent=2) if bifurcation_report else "Not available",
            interpreter_claim="yes" if interpreter_claim else ("no" if interpreter_claim is not None else "unknown"),
        )

        result = self.invoke(
            prompt,
            organism_id=organism_id,
            experiment_id=experiment_id,
        )
        return result.parsed

    def _parse_response(self, raw_output: str) -> dict[str, Any]:
        # Try JSON extraction
        import re
        match = re.search(r"```json\s*\n(.*?)```", raw_output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Fallback
        lower = raw_output.lower()
        return {
            "verified": "verified" in lower and "not verified" not in lower,
            "confidence": 0.5,
            "reasoning": raw_output[:500],
            "raw": raw_output,
        }


def _summarize_for_verification(results_data: dict[str, Any]) -> str:
    """Summarize results focusing on data the verifier needs."""
    lines = []
    if "sweep_param" in results_data:
        lines.append(f"Parameter sweep over: {results_data['sweep_param']}")
        lines.append(f"Values tested: {results_data['param_values']}")
        for pval, seeds in results_data.get("results", {}).items():
            for seed, r in seeds.items():
                n_contribs = len(r.get("neuron_contributions", []))
                if n_contribs > 0:
                    # Show neuron contribution norms
                    import numpy as np
                    contribs = np.array(r["neuron_contributions"])
                    norms = np.linalg.norm(contribs, axis=0)
                    sorted_norms = np.sort(norms)[::-1][:8]
                    norms_str = ", ".join(f"{n:.3f}" for n in sorted_norms)
                    lines.append(
                        f"  {results_data['sweep_param']}={pval}: "
                        f"loss={r['final_loss']:.6f}, "
                        f"top neuron norms=[{norms_str}]"
                    )
    return "\n".join(lines)


VERIFY_PROMPT = """\
Independently determine whether bifurcation occurred in these experiment results.

## Experiment Data
{results_summary}

## Automated Detector Report
{auto_report}

## Interpreter's Claim
The interpreter claimed bifurcation was detected: {interpreter_claim}

## Instructions

Examine the data independently. Bifurcation means a SUDDEN qualitative \
reorganization — neurons abruptly switching from one representational strategy \
to another as a parameter changes continuously. Look for:
1. Abrupt changes in neuron contribution patterns between consecutive parameter values
2. Sudden redistribution of which neurons carry most of the representation
3. Qualitative (not just quantitative) changes in the learned function's structure

Provide your verdict as a JSON object:
```json
{{
    "verified": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "...",
    "bifurcation_points": [list of parameter values where bifurcation occurs, or empty],
    "evidence": ["specific pieces of evidence supporting your conclusion"]
}}
```"""
