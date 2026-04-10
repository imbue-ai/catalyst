"""Experiment result interpretation agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import LLMAgent


SYSTEM_PROMPT = """\
You are a scientific experiment interpreter specializing in neural network \
bifurcation phenomena. You analyze experiment results from shallow (two-layer) \
ReLU MLP training runs and produce structured interpretations.

Your analysis must be grounded in the specific numerical data provided. \
Do not speculate beyond what the data shows."""


class InterpreterAgent(LLMAgent):
    """Interprets experiment results in the context of a theory."""

    agent_type = "interpreter"

    def __init__(self, **kwargs):
        kwargs.setdefault("system_prompt", SYSTEM_PROMPT)
        kwargs.setdefault("temperature", 0.3)
        super().__init__(**kwargs)

    def interpret(
        self,
        theory_text: str,
        experiment_params: dict[str, Any],
        results_data: dict[str, Any],
        bifurcation_report: dict[str, Any] | None = None,
        organism_id: str | None = None,
        experiment_id: str | None = None,
    ) -> dict[str, Any]:
        """Interpret experiment results against a theory.

        Returns a dict with keys: observations, bifurcation_detected,
        theory_support, suggested_followups, summary.
        """
        prompt = INTERPRET_PROMPT.format(
            theory=theory_text,
            params=json.dumps(experiment_params, indent=2),
            results_summary=_summarize_results(results_data),
            bifurcation_report=json.dumps(bifurcation_report, indent=2) if bifurcation_report else "Not available",
        )

        result = self.invoke(
            prompt,
            organism_id=organism_id,
            experiment_id=experiment_id,
        )
        return result.parsed

    def _parse_response(self, raw_output: str) -> dict[str, Any]:
        """Extract structured interpretation from LLM output."""
        # Try to find JSON block
        parsed = _try_parse_json(raw_output)
        if parsed:
            return parsed

        # Fallback: extract sections from markdown
        return {
            "observations": _extract_section(raw_output, "observations", "observation"),
            "bifurcation_detected": "bifurcation" in raw_output.lower() and "detected" in raw_output.lower() and "not detected" not in raw_output.lower(),
            "theory_support": _extract_section(raw_output, "theory support", "theory"),
            "suggested_followups": _extract_section(raw_output, "follow-up", "suggestion"),
            "summary": raw_output[:500],
            "raw": raw_output,
        }


def _summarize_results(results_data: dict[str, Any]) -> str:
    """Create a concise summary of experiment results for the prompt."""
    lines = []
    if "sweep_param" in results_data:
        lines.append(f"Sweep parameter: {results_data['sweep_param']}")
        lines.append(f"Values: {results_data['param_values']}")
        for pval, seeds in results_data.get("results", {}).items():
            for seed, r in seeds.items():
                lines.append(f"  {results_data['sweep_param']}={pval}, seed={seed}: "
                           f"final_loss={r['final_loss']:.6f}, width={r['width']}")
    else:
        lines.append(f"Single run: width={results_data.get('width')}, "
                     f"lr={results_data.get('lr')}, "
                     f"final_loss={results_data.get('final_loss', 'N/A')}")
    return "\n".join(lines)


def _try_parse_json(text: str) -> dict | None:
    """Try to extract a JSON object from text."""
    # Look for ```json blocks
    import re
    match = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Try the whole text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    return None


def _extract_section(text: str, *keywords: str) -> str:
    """Extract a section from markdown text by heading keywords."""
    lines = text.split("\n")
    capturing = False
    captured = []
    for line in lines:
        lower = line.lower().strip()
        if any(kw in lower for kw in keywords) and (lower.startswith("#") or lower.startswith("**")):
            capturing = True
            continue
        elif capturing and (line.startswith("#") or line.startswith("**")):
            break
        elif capturing:
            captured.append(line)
    return "\n".join(captured).strip() if captured else ""


INTERPRET_PROMPT = """\
Analyze the following experiment results in the context of the theory being tested.

## Theory Under Test
{theory}

## Experiment Parameters
{params}

## Results Summary
{results_summary}

## Automated Bifurcation Report
{bifurcation_report}

## Instructions

Provide your analysis as a JSON object with these fields:
- "observations": A list of specific observations from the data (strings)
- "bifurcation_detected": Boolean — did you observe bifurcation in these results?
- "theory_support": One of "supports", "contradicts", "inconclusive", or "partially_supports"
- "theory_support_reasoning": Explanation of how these results relate to the theory
- "suggested_followups": List of suggested follow-up experiments (strings)
- "summary": 2-3 sentence summary of findings

Return ONLY the JSON object wrapped in ```json``` markers."""
