"""Cross-cutting evidence reviewer agent.

Directly inspired by knowledge_seeker's reviewer.py: after an experiment
completes, the reviewer checks the results against ALL organisms in the
population — not just the one being tested. This allows a single experiment
to produce evidence for/against multiple theories (multiplier effect).

Uses batched review (groups of organisms) and parallel execution.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .base import LLMAgent


SYSTEM_PROMPT = """\
You are a cross-cutting evidence reviewer. Given experiment results, you \
evaluate how they relate to EACH of the provided theories — not just the \
one that motivated the experiment. A single experiment can provide evidence \
for or against many theories simultaneously.

Be calibrated: only assign non-zero confidence deltas when the experiment \
genuinely says something about the theory. Most theories will be unaffected \
by any given experiment."""


class ReviewerAgent(LLMAgent):
    """Reviews experiment results against all theories in population."""

    agent_type = "reviewer"

    def __init__(self, **kwargs):
        kwargs.setdefault("system_prompt", SYSTEM_PROMPT)
        kwargs.setdefault("temperature", 0.2)
        kwargs.setdefault("max_tokens", 4096)
        super().__init__(**kwargs)

    def review_cross_cutting(
        self,
        experiment_summary: str,
        bifurcation_report: dict[str, Any] | None,
        theories: list[dict[str, str]],  # [{id, theory_text}, ...]
        batch_size: int = 10,
        max_workers: int = 4,
    ) -> list[dict[str, Any]]:
        """Review experiment results against multiple theories.

        Returns list of evidence dicts: [{organism_id, confidence_delta, explanation}, ...]
        Batches theories and processes in parallel (knowledge_seeker pattern).
        """
        if not theories:
            return []

        all_evidence = []

        # Process in batches with parallel execution
        batches = [
            theories[i:i + batch_size]
            for i in range(0, len(theories), batch_size)
        ]

        if len(batches) == 1:
            # Single batch — no need for threading
            return self._review_batch(experiment_summary, bifurcation_report, batches[0])

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    self._review_batch,
                    experiment_summary,
                    bifurcation_report,
                    batch,
                )
                for batch in batches
            ]
            for future in futures:
                try:
                    all_evidence.extend(future.result())
                except Exception:
                    pass  # Skip failed batches

        return all_evidence

    def _review_batch(
        self,
        experiment_summary: str,
        bifurcation_report: dict[str, Any] | None,
        theories: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Review a single batch of theories."""
        theories_text = "\n\n".join(
            f"### Theory {t['id']}\n{t['theory_text'][:500]}"
            for t in theories
        )

        prompt = REVIEW_PROMPT.format(
            experiment_summary=experiment_summary,
            bifurcation_report=json.dumps(bifurcation_report, indent=2) if bifurcation_report else "Not available",
            theories=theories_text,
        )

        result = self.invoke(prompt)
        return result.parsed if isinstance(result.parsed, list) else []

    def _parse_response(self, raw_output: str) -> list[dict[str, Any]]:
        import re

        match = re.search(r"```json\s*\n(.*?)```", raw_output, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if isinstance(data, dict) and "cross_evidence" in data:
                    return data["cross_evidence"]
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
        return []


REVIEW_PROMPT = """\
Review the following experiment results against ALL theories listed below. \
For each theory, determine if this experiment provides any evidence for or \
against it.

## Experiment Results
{experiment_summary}

## Bifurcation Report
{bifurcation_report}

## Theories to Review
{theories}

## Instructions

For each theory where this experiment provides meaningful evidence, output \
an evidence entry. Skip theories that are unaffected by this experiment.

Return a JSON object:
```json
{{
    "cross_evidence": [
        {{
            "organism_id": "the theory ID",
            "confidence_delta": 0.3,
            "explanation": "How this experiment relates to this theory..."
        }}
    ]
}}
```

confidence_delta ranges from -1.0 (strongly contradicts) to +1.0 (strongly supports). \
Use 0 or omit theories where the experiment is irrelevant. Most theories should \
be unaffected by any given experiment — be conservative."""
