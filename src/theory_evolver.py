"""Domain-specific ``darwinian_evolver`` types for theory evolution.

Concrete subclasses of ``darwinian_evolver``'s
base types that wrap ai-scientist identifiers (theory IDs, review IDs).

Unlike the multiverse model, ai-scientist evaluations do not (yet) decompose
into segments, so ``TheoryEvaluationResult`` stores a single top-level ``score``
plus a free-form ``subscores`` dict — no segment-score list.
"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field, model_validator

from darwinian_evolver.problem import (
    EvaluationFailureCase,
    EvaluationResult,
    Organism,
)


class TheoryOrganism(Organism):
    """An organism that wraps a single theory artifact in the context_manager DB."""

    theory_id: str = Field(
        description="Theory ID (e.g. 'T_20260414_143100_d4e5f6') stored in the context_manager DB."
    )


class TheoryFailureCase(EvaluationFailureCase):
    """A failure case produced while evaluating a theory.

    References the review (typically a falsification report) that identified
    the failure. ``data_point_id`` (inherited from the base) defaults to the
    review ID so the base class's de-duplication / re-evaluation machinery
    keys off the same identifier.
    """

    review_id: str = Field(
        description="Review ID (e.g. 'R_20260414_143200_g7h8i9') stored in the context_manager DB."
    )

    @model_validator(mode="before")
    @classmethod
    def _default_data_point_id_to_review_id(cls, data: Any) -> Any:
        if (
            isinstance(data, dict)
            and data.get("data_point_id") is None
            and data.get("review_id") is not None
        ):
            data["data_point_id"] = data["review_id"]
        return data


class TheoryEvaluationResult(EvaluationResult):
    """Mutable evaluation result for a theory.

    We continually rescore theories as new evidence comes in, so this type
    overrides the base's ``frozen=True`` config with ``frozen=False`` —
    mirroring ``KnowledgeEvaluationResult`` on the multiverse branch.

    Holds the inherited top-level ``score`` (used for parent sampling in the
    Population) and an open ``subscores`` dict for arbitrary named components
    (e.g. ``{"prediction_accuracy": 0.72, "soundness": 0.9}``). No segment
    score list — ai-scientist evaluations are single-shot for now.
    """

    model_config = ConfigDict(frozen=False)

    subscores: dict[str, float] = Field(
        default_factory=dict,
        description="Named subscore components. Arbitrary keys; useful for debugging.",
    )
