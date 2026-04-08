"""Organism data model and filesystem operations.

Design informed by imbue-ai/knowledge_seeker:
- Evidence as first-class objects with confidence deltas (not binary pass/fail)
- Conservative confidence scaling (positive evidence scaled 0.5x)
- Hypothesis expiration after N failed validation attempts
- Atomic persistence via os.replace for crash recovery
- Dismissed organisms can be refined/salvaged, not just deleted
"""

from __future__ import annotations

import dataclasses
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(value, max_val))


@dataclasses.dataclass
class Evidence:
    """A single piece of evidence for or against an organism's theory.

    Modeled after knowledge_seeker's Evidence: each piece of evidence carries
    a confidence delta (not binary), an explanation, and a link to the
    experiment that produced it.
    """
    id: str
    experiment_id: str
    confidence_delta: float  # [-1.0, 1.0]: positive supports, negative refutes
    explanation: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evidence:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclasses.dataclass
class ExperimentRecord:
    """Record of a single experiment run against an organism."""
    id: str
    params: dict[str, Any]
    results_path: Path
    interpretation: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "params": self.params,
            "results_path": str(self.results_path),
            "interpretation": self.interpretation,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentRecord:
        return cls(
            id=data["id"],
            params=data["params"],
            results_path=Path(data["results_path"]),
            interpretation=data.get("interpretation", ""),
            timestamp=data["timestamp"],
        )


@dataclasses.dataclass
class Organism:
    """A theory organism — a hypothesis with its evidence and scores."""
    id: str
    parent_id: str | None
    theory_path: Path
    scorer_path: Path
    metadata: dict[str, Any]
    experiments: list[ExperimentRecord]
    evidence: list[Evidence]
    scores: dict[str, Any]
    directory: Path

    # Continuous confidence score [-1.0, 1.0], updated by evidence deltas.
    # Inspired by knowledge_seeker's hypothesis confidence model.
    confidence: float = 0.0

    # How many experiment cycles have tested this organism
    validation_attempts: int = 0

    @property
    def generation(self) -> int:
        return self.metadata.get("generation", 0)

    @property
    def theory_text(self) -> str:
        return self.theory_path.read_text()

    @property
    def scorer_code(self) -> str:
        return self.scorer_path.read_text()

    @property
    def status(self) -> str:
        """Derive status from confidence thresholds (knowledge_seeker pattern)."""
        if self.confidence >= 0.75:
            return "validated"
        elif self.confidence <= -0.5:
            return "dismissed"
        return "active"

    def apply_evidence(
        self,
        evidence: Evidence,
        positive_scaling: float = 0.5,
    ) -> None:
        """Apply evidence to update confidence.

        Uses knowledge_seeker's conservative scaling: positive evidence is
        scaled down (default 0.5x) to prevent overconfidence from single
        experiments. Requires multiple confirmations for high confidence.
        """
        self.evidence.append(evidence)
        self.validation_attempts += 1

        delta = evidence.confidence_delta
        if delta > 0:
            delta *= positive_scaling

        self.confidence = _clamp(self.confidence + delta, -1.0, 1.0)

    def combined_score(self) -> float:
        """Compute combined fitness score with exploration floor.

        Uses knowledge_seeker's minimum score floor to prevent starvation
        of low-scoring organisms (maintains exploration pressure).
        """
        quantitative = self.scores.get("quantitative", 0.0)
        qualitative = self.scores.get("qualitative", {})
        if isinstance(qualitative, dict):
            qual_scores = [
                qualitative.get("specificity", 0),
                qualitative.get("generality", 0),
                qualitative.get("mechanistic_depth", 0),
                qualitative.get("falsifiability", 0),
            ]
            qual_avg = sum(qual_scores) / max(len(qual_scores), 1)
        else:
            qual_avg = float(qualitative) if qualitative else 0.0

        raw = 0.6 * quantitative + 0.4 * qual_avg

        # Exploration floor: even low-scoring organisms get minimum probability
        # (knowledge_seeker pattern: max(0.1, utility))
        return max(0.1, raw)

    def next_experiment_id(self) -> str:
        """Generate the next experiment ID for this organism."""
        existing = [int(e.id.split("_")[1]) for e in self.experiments if "_" in e.id]
        n = max(existing, default=0) + 1
        return f"exp_{n:03d}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "theory_path": str(self.theory_path),
            "scorer_path": str(self.scorer_path),
            "metadata": self.metadata,
            "experiments": [e.to_dict() for e in self.experiments],
            "evidence": [e.to_dict() for e in self.evidence],
            "scores": self.scores,
            "confidence": self.confidence,
            "validation_attempts": self.validation_attempts,
        }


def _generate_organism_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:6]
    return f"org_{ts}_{short}"


def _atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON atomically via temp file + os.replace (knowledge_seeker pattern)."""
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2))
    os.replace(str(tmp_path), str(path))


def load_organism(directory: Path) -> Organism:
    """Load an organism from its directory."""
    meta_path = directory / "metadata.json"
    meta = json.loads(meta_path.read_text())

    # Load experiments
    experiments = []
    exp_dir = directory / "experiments"
    if exp_dir.exists():
        for exp_path in sorted(exp_dir.iterdir()):
            if not exp_path.is_dir():
                continue
            exp_meta_path = exp_path / "params.json"
            if not exp_meta_path.exists():
                continue
            params = json.loads(exp_meta_path.read_text())
            interpretation = ""
            interp_path = exp_path / "interpretation.md"
            if interp_path.exists():
                interpretation = interp_path.read_text()
            experiments.append(ExperimentRecord(
                id=exp_path.name,
                params=params,
                results_path=exp_path / "results.json",
                interpretation=interpretation,
                timestamp=params.get("timestamp", ""),
            ))

    # Load scores
    scores_path = directory / "scores.json"
    scores = json.loads(scores_path.read_text()) if scores_path.exists() else {}

    # Load evidence
    evidence_path = directory / "evidence.json"
    evidence = []
    if evidence_path.exists():
        for e in json.loads(evidence_path.read_text()):
            evidence.append(Evidence.from_dict(e))

    return Organism(
        id=meta["id"],
        parent_id=meta.get("parent_id"),
        theory_path=directory / "theory.md",
        scorer_path=directory / "scorer.py",
        metadata=meta,
        experiments=experiments,
        evidence=evidence,
        scores=scores,
        directory=directory,
        confidence=meta.get("confidence", 0.0),
        validation_attempts=meta.get("validation_attempts", 0),
    )


def create_organism(
    theory_text: str,
    scorer_code: str,
    organisms_dir: Path,
    parent: Organism | None = None,
) -> Organism:
    """Create a new organism directory with all required files."""
    org_id = _generate_organism_id()
    org_dir = organisms_dir / org_id
    org_dir.mkdir(parents=True, exist_ok=True)
    (org_dir / "experiments").mkdir(exist_ok=True)

    generation = (parent.generation + 1) if parent else 0
    lineage = list(parent.metadata.get("lineage", [])) if parent else []
    if parent:
        lineage.append(parent.id)

    metadata = {
        "id": org_id,
        "parent_id": parent.id if parent else None,
        "generation": generation,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lineage": lineage,
        "confidence": 0.0,
        "validation_attempts": 0,
    }

    # Atomic writes for crash recovery (knowledge_seeker pattern)
    _atomic_write_json(org_dir / "metadata.json", metadata)
    (org_dir / "theory.md").write_text(theory_text)
    (org_dir / "scorer.py").write_text(scorer_code)
    _atomic_write_json(org_dir / "scores.json", {})
    _atomic_write_json(org_dir / "evidence.json", [])

    return load_organism(org_dir)


def save_organism_scores(organism: Organism, scores: dict[str, Any]) -> None:
    """Update an organism's scores on disk (atomic write)."""
    organism.scores.update(scores)
    _atomic_write_json(organism.directory / "scores.json", organism.scores)


def save_organism_state(organism: Organism) -> None:
    """Persist confidence, validation_attempts, and evidence to disk."""
    # Update metadata
    meta = organism.metadata.copy()
    meta["confidence"] = organism.confidence
    meta["validation_attempts"] = organism.validation_attempts
    _atomic_write_json(organism.directory / "metadata.json", meta)

    # Persist evidence
    _atomic_write_json(
        organism.directory / "evidence.json",
        [e.to_dict() for e in organism.evidence],
    )


def save_experiment(
    organism: Organism,
    experiment_id: str,
    params: dict[str, Any],
    results_data: dict[str, Any] | None = None,
    interpretation: str = "",
    bifurcation_report: dict[str, Any] | None = None,
) -> ExperimentRecord:
    """Save an experiment to an organism's directory."""
    exp_dir = organism.directory / "experiments" / experiment_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    (exp_dir / "plots").mkdir(exist_ok=True)

    params["timestamp"] = datetime.now(timezone.utc).isoformat()
    _atomic_write_json(exp_dir / "params.json", params)

    if results_data:
        _atomic_write_json(exp_dir / "results.json", results_data)

    if interpretation:
        (exp_dir / "interpretation.md").write_text(interpretation)

    if bifurcation_report:
        _atomic_write_json(exp_dir / "bifurcation_report.json", bifurcation_report)

    record = ExperimentRecord(
        id=experiment_id,
        params=params,
        results_path=exp_dir / "results.json",
        interpretation=interpretation,
        timestamp=params["timestamp"],
    )
    organism.experiments.append(record)
    return record


def expire_stale_organisms(
    organisms: list[Organism],
    max_validation_attempts: int = 6,
) -> list[Organism]:
    """Auto-dismiss organisms that haven't validated after N attempts.

    Knowledge_seeker pattern: prevents population bloat from dead-end theories.
    Returns dismissed organisms (for potential refinement).
    """
    dismissed = []
    for org in organisms:
        if org.status == "active" and org.validation_attempts >= max_validation_attempts:
            org.confidence = -0.6  # Push below dismissed threshold
            save_organism_state(org)
            dismissed.append(org)
    return dismissed


def list_organisms(organisms_dir: Path) -> list[Organism]:
    """Load all organisms from the organisms directory."""
    if not organisms_dir.exists():
        return []
    organisms = []
    for d in sorted(organisms_dir.iterdir()):
        if d.is_dir() and (d / "metadata.json").exists():
            try:
                organisms.append(load_organism(d))
            except (json.JSONDecodeError, KeyError, FileNotFoundError):
                continue
    return organisms
