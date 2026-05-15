"""Agent Context Manager — filesystem-based persistence and context assembly for the Skills pipeline.

Run with ``--help`` to see the available CLI subcommands.

This command is intentionally contained within a single Python file, to make sure that it can be run
reliably through a symlink or copy from within a skill's scripts folder.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import stat
import sys
import time
from typing import Literal
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, computed_field

from darwinian_evolver.population import Population, WeightedSamplingPopulation
from darwinian_evolver.problem import (
    EvaluationResult,
    Organism,
    EvaluationFailureCase,
)


# ---------------------------------------------------------------------------
# Constants & configuration
# ---------------------------------------------------------------------------

AGENT_TYPE_MAP: dict[str, str] = {
    # agent_type -> database_category
    "explorer": "exploration",
    "literature-review": "literature",
    "search-literature": "literature",
    "write-theory": "theory",
    "refine-hypothesis": "theory",
    "falsify-hypothesis": "review",
    "suggest-expansions": "review",
    "expand-theory": "theory",
    "polish-theory": "theory",
    "edit-theory": "theory",
    "streamline-theory": "theory",
    "support-idea": "theory",
    "import-theory": "theory",
    "run-experiment": "experiment",
    "predict-experiments": "prediction",
}

CATEGORY_MD_MAP: dict[str, str] = {
    "exploration": "report.md",
    "literature": "summary.md",
    "theory": "theory.md",
    "review": "review.md",
    "experiment": "description.md",
    "prediction": "predictions.md",
}

ID_PREFIXES: dict[str, str] = {
    "exploration": "E",
    "literature": "L",
    "theory": "T",
    "review": "R",
    "experiment": "X",
    "prediction": "P",
}

PREFIX_TO_CATEGORY: dict[str, str] = {v: k for k, v in ID_PREFIXES.items()}

VALID_CATEGORIES: tuple[str, ...] = (
    "exploration",
    "literature",
    "theory",
    "review",
    "experiment",
    "prediction",
)

DEFAULT_DB_DIR = ".ai-scientist-db"
ENV_DB_PATH = "AI_SCIENTIST_DB_PATH"
LOCK_FILENAME = ".lock"
IGNORE_METADATA_PATTERN = shutil.ignore_patterns("metadata.json")

POPULATION_FILENAME = "population.snapshot"
SCORE_DECAY_RATE = 0.8

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_db_path(ensure_exists: bool = True) -> Path:
    """Return the resolved database root path."""
    env = os.environ.get(ENV_DB_PATH)
    if env:
        path = Path(env).resolve()
    else:
        path = Path.cwd() / DEFAULT_DB_DIR

    if ensure_exists and not path.is_dir():
        raise RuntimeError(
            f"Database path does not exist: {path}\n"
            "Please initialize it first by running: context_manager init"
        )
    return path


def generate_id(category: str) -> str:
    """Generate a unique ID like ``E_20260414_143052_a1b2c3``."""
    prefix = ID_PREFIXES[category]
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"{prefix}_{ts}_{suffix}"


# ---------------------------------------------------------------------------
# Database lock
# ---------------------------------------------------------------------------


_db_lock_held_count = 0


class DatabaseLock:
    """Context manager that acquires an exclusive advisory lock on the DB."""

    def __init__(self, db_root: Path, timeout: float = 30.0) -> None:
        self.lock_path = db_root / LOCK_FILENAME
        self.timeout = timeout
        self._fd: int | None = None

    def __enter__(self) -> "DatabaseLock":
        global _db_lock_held_count
        if _db_lock_held_count > 0:
            _db_lock_held_count += 1
            return self

        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                _db_lock_held_count += 1
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    os.close(self._fd)
                    self._fd = None
                    raise TimeoutError(
                        f"Could not acquire database lock within {self.timeout}s"
                    )
                time.sleep(0.05)

    def __exit__(self, *_exc: object) -> None:
        global _db_lock_held_count
        if _db_lock_held_count > 0:
            _db_lock_held_count -= 1
            if _db_lock_held_count == 0 and self._fd is not None:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
                self._fd = None


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class StoredMetadata(BaseModel):
    """Metadata written alongside every stored result."""

    id: str
    agent_type: str
    category: str
    created_at: str
    headline: str = ""
    parent_theory: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)
    staged_for_transaction: str | None = None


class DatabaseSession:
    """A view of the database providing transactional isolation and population state."""

    def __init__(self, db_root: Path):
        self.db_root = db_root
        self.tx_id = os.environ.get("CONTEXT_TRANSACTION_ID")
        self._lock = DatabaseLock(db_root)
        self._population: Population | None = None
        self._population_loaded = False
        self._population_modified = False

    def __enter__(self) -> "DatabaseSession":
        self._lock.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if (
            exc_type is None
            and self._population_modified
            and self._population is not None
        ):
            _save_population(self._population, self.db_root / POPULATION_FILENAME)
        self._lock.__exit__(exc_type, exc_val, exc_tb)

    def is_visible(self, data: dict) -> bool:
        """Return True if the object is committed or staged for the current transaction."""
        staged = data.get("staged_for_transaction")
        if not staged:
            return True
        return staged == self.tx_id

    def get_metadata(self, category: str, item_id: str) -> dict | None:
        """Safely fetch and parse metadata if visible."""
        meta_path = self.db_root / category / item_id / "metadata.json"
        if not meta_path.is_file():
            return None
        try:
            data = json.loads(meta_path.read_text())
            if self.is_visible(data):
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return None

    def iter_metadata(self, category: str, include_uncommitted: bool = False):
        """Iterate over all visible metadata in a category."""
        cat_dir = self.db_root / category
        if not cat_dir.is_dir():
            return
        for meta_path in cat_dir.glob("*/metadata.json"):
            try:
                data = json.loads(meta_path.read_text())
                if include_uncommitted or self.is_visible(data):
                    yield meta_path, data
            except (json.JSONDecodeError, OSError):
                continue

    def iter_all_metadata(self, include_uncommitted: bool = False):
        """Iterate over all visible metadata in all categories."""
        for category in VALID_CATEGORIES:
            yield from self.iter_metadata(
                category, include_uncommitted=include_uncommitted
            )

    def get_population(self) -> Population | None:
        """Lazy-load the population snapshot."""
        if not self._population_loaded:
            self._population = _load_population(self.db_root / POPULATION_FILENAME)
            self._population_loaded = True
        return self._population

    def set_population(self, pop: Population) -> None:
        """Explicitly set and mark the population as modified."""
        self._population = pop
        self._population_loaded = True
        self._population_modified = True

    def mark_population_modified(self) -> None:
        """Flag the population for saving on session exit."""
        self._population_modified = True

    def record_theory(self, theory_id: str, parent_theory_id: str | None) -> None:
        """Add a newly-stored theory to the population state."""
        pop = self.get_population()
        if pop is None:
            if parent_theory_id is not None:
                raise RuntimeError(
                    f"Attempting to record child theory {theory_id!r} with parent "
                    f"{parent_theory_id!r} but no population exists yet."
                )
            organism = TheoryOrganism(theory_id=theory_id)
            result = TheoryEvaluationResult(score=0.0, trainable_failure_cases=[])
            pop = WeightedSamplingPopulation(
                organism,
                result,
                midpoint_score_percentile=None,
                fixed_midpoint_score=0.5,
                sharpness=10.0,
            )
            self.set_population(pop)
            return

        parent_org: TheoryOrganism | None = None
        if parent_theory_id is not None:
            found = _find_organism_by_theory_id(pop, parent_theory_id)
            if found is None:
                raise RuntimeError(
                    f"Parent theory {parent_theory_id!r} is not in the population; "
                    f"refusing to add child {theory_id!r}"
                )
            parent_org, _ = found

        organism = TheoryOrganism(theory_id=theory_id, parent=parent_org)
        result = TheoryEvaluationResult(score=0.0, trainable_failure_cases=[])
        pop.add(organism, result)
        self.mark_population_modified()

    def record_review(self, theory_id: str | None, review_id: str) -> None:
        """Attach a newly-stored review to its parent theory in the population."""
        if theory_id is None:
            raise RuntimeError(
                f"Attempting to record review {review_id!r} without a parent theory."
            )
        pop = self.get_population()
        if pop is None:
            raise RuntimeError(
                f"Attempting to record review {review_id!r} for theory {theory_id!r} but no population exists yet."
            )
        found = _find_organism_by_theory_id(pop, theory_id)
        if found is None:
            raise RuntimeError(
                f"Parent theory {theory_id!r} for review {review_id!r} is not in the population."
            )
        _, result = found
        assert isinstance(result, TheoryEvaluationResult)
        result.trainable_failure_cases.append(
            TheoryEvaluationFailureCase(review_id=review_id, data_point_id=review_id)
        )
        self.mark_population_modified()


def copy_artifact(src: Path, dst: Path, exclude_results: bool = False) -> None:
    """Helper to copy an artifact, optionally omitting results, and restoring write permissions."""
    if dst.exists():
        raise ValueError(f"Destination already exists: {dst}")

    ignore_pattern = IGNORE_METADATA_PATTERN
    if exclude_results:
        # Ignore everything that's NOT either "script.py" or "description.md"
        ignore_pattern = lambda _, names: [  # noqa: E731
            n for n in names if n not in ("script.py", "description.md")
        ]

    shutil.copytree(src, dst, ignore=ignore_pattern)
    _make_writable(dst)


class TheoryOrganism(Organism):
    """An organism that wraps a single theory artifact in the context_manager DB."""

    theory_id: str = Field(
        description="Theory ID (e.g. 'T_20260414_143100_d4e5f6') stored in the context_manager DB."
    )

    @computed_field
    @property
    def visualizer_props(self) -> dict[str, str | float]:
        """Additional properties that should be included in the organism info and tooltip."""
        return {"theory_id": self.theory_id}


class TheoryEvaluationResult(EvaluationResult):
    """Mutable evaluation result for a theory.

    We continually rescore theories as new evidence comes in, so this type
    overrides the base's ``frozen=True`` config with ``frozen=False``.

    Holds the inherited top-level ``score`` (used for parent sampling in the
    Population) and an open ``subscores`` dict for arbitrary named components
    (e.g. ``{"prediction_accuracy": 0.72, "soundness": 0.9}``).
    """

    model_config = ConfigDict(frozen=False)

    subscores: dict[str, float] = Field(
        default_factory=dict,
        description="Named subscore components.",
    )

    @computed_field
    @property
    def visualizer_props(self) -> dict[str, str | float]:
        """Additional properties that should be included in the organism evaluation info and tooltip."""
        return self.subscores


class TheoryEvaluationFailureCase(EvaluationFailureCase):
    """Represents a review that has been performed on a theory."""

    review_id: str = Field(
        description="Review ID (e.g. 'R_20260414_150000_a1b2c3') stored in the context_manager DB."
    )


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------


MAKE_READONLY = False


def _make_readonly(path: Path) -> None:
    """Recursively remove write permissions from *path*."""
    if not MAKE_READONLY:
        return
    for root, dirs, files in os.walk(path):
        for name in files:
            fp = os.path.join(root, name)
            current = os.stat(fp).st_mode
            os.chmod(fp, current & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        for name in dirs:
            dp = os.path.join(root, name)
            current = os.stat(dp).st_mode
            os.chmod(dp, current & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    # The root directory itself
    current = os.stat(path).st_mode
    os.chmod(path, current & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _make_writable(path: Path) -> None:
    """Recursively restore owner-write permissions on *path*.

    Used after copying from the immutable database so the downstream agent
    can freely modify its working copy.
    """
    current = os.stat(path).st_mode
    os.chmod(path, current | stat.S_IWUSR)
    for root, dirs, files in os.walk(path):
        for name in dirs:
            dp = os.path.join(root, name)
            current = os.stat(dp).st_mode
            os.chmod(dp, current | stat.S_IWUSR)
        for name in files:
            fp = os.path.join(root, name)
            current = os.stat(fp).st_mode
            os.chmod(fp, current | stat.S_IWUSR)


def _population_path(db_root: Path) -> Path:
    return db_root / POPULATION_FILENAME


def _save_population(population: Population, path: Path) -> None:
    """Serialize the population via ``Population.snapshot()`` to a binary file."""
    path.write_bytes(population.snapshot())


def _find_organism_by_theory_id(
    population: Population, theory_id: str
) -> tuple[TheoryOrganism, TheoryEvaluationResult] | None:
    for organism, result in population.organisms:
        if organism.theory_id == theory_id:
            assert isinstance(organism, TheoryOrganism)
            assert isinstance(result, TheoryEvaluationResult)
            return organism, result
    return None


def _load_population(path: Path) -> Population | None:
    """Restore the population via ``Population.from_snapshot()``, or return None."""
    if not path.is_file():
        return None
    return WeightedSamplingPopulation.from_snapshot(path.read_bytes())


def store_results(
    from_agent_type: str,
    from_folder: Path,
    parent_theory: str | None = None,
    metadata_extra: dict[str, str] | None = None,
) -> str:
    """Persist agent output into the immutable database. Returns the new ID."""
    if from_agent_type not in AGENT_TYPE_MAP:
        raise ValueError(
            f"Unknown agent type {from_agent_type!r}. "
            f"Must be one of: {', '.join(AGENT_TYPE_MAP)}"
        )

    category = AGENT_TYPE_MAP[from_agent_type]
    expected_md = CATEGORY_MD_MAP[category]

    # --- validate source folder ---
    if not from_folder.is_dir():
        raise ValueError(f"Source folder does not exist: {from_folder}")
    if not (from_folder / expected_md).is_file():
        raise ValueError(
            f"Source folder is missing the required file {expected_md!r}: {from_folder}"
        )

    db_root = get_db_path()

    # --- agents required/allowed to attach a parent_theory ---
    parent_theory_required_agents = (
        "falsify-hypothesis",
        "suggest-expansions",
        "predict-experiments",
        "refine-hypothesis",
        "polish-theory",
        "edit-theory",
        "streamline-theory",
        "expand-theory",
    )
    parent_theory_allowed_agents = parent_theory_required_agents + (
        "run-experiment",
        "support-idea",
    )

    if from_agent_type in parent_theory_required_agents and not parent_theory:
        raise ValueError(
            f"--parent_theory is required when storing {from_agent_type} results"
        )
    if parent_theory and from_agent_type in parent_theory_allowed_agents:
        theory_dir = db_root / "theory" / parent_theory
        if not theory_dir.is_dir():
            raise ValueError(
                f"Referenced parent theory {parent_theory!r} does not exist "
                f"in the database (expected {theory_dir})"
            )

    with DatabaseSession(db_root) as session:
        new_id = generate_id(category)

        # --- determine target directory ---
        if category in VALID_CATEGORIES:
            target_dir = db_root / category / new_id
        else:
            raise RuntimeError(f"Unknown category {category!r}")

        if target_dir.exists():
            raise RuntimeError(
                f"ID collision: {target_dir} already exists (this should be extremely rare)"
            )

        # --- ensure intermediate dirs exist ---
        target_dir.parent.mkdir(parents=True, exist_ok=True)

        # --- copy files ---
        shutil.copytree(from_folder, target_dir, ignore=IGNORE_METADATA_PATTERN)

        # --- extract headline ---
        headline = ""
        primary_md_path = target_dir / expected_md
        if primary_md_path.is_file():
            try:
                with open(primary_md_path, "r", encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        headline = first_line.lstrip("#").strip()
            except Exception:
                pass

        # --- write metadata ---
        meta = StoredMetadata(
            id=new_id,
            agent_type=from_agent_type,
            category=category,
            created_at=datetime.now(timezone.utc).isoformat(),
            headline=headline,
            parent_theory=parent_theory
            if from_agent_type in parent_theory_allowed_agents
            else None,
            extra=metadata_extra or {},
            staged_for_transaction=session.tx_id,
        )
        (target_dir / "metadata.json").write_text(
            json.dumps(meta.model_dump(), indent=2) + "\n"
        )

        # --- make immutable ---
        _make_readonly(target_dir)

        # --- add to the theory population ---
        if not session.tx_id:
            if category == "theory":
                session.record_theory(
                    theory_id=new_id,
                    parent_theory_id=parent_theory,
                )
            elif category == "review":
                session.record_review(
                    theory_id=parent_theory,
                    review_id=new_id,
                )

    return new_id


def _get_ancestor_theories(
    session: DatabaseSession, base_theories: list[str]
) -> set[str]:
    """Recursively collect the given theories and all of their ancestors."""
    target_theories = set(base_theories)
    to_visit = list(target_theories)
    while to_visit:
        curr_tid = to_visit.pop()
        tdata = session.get_metadata("theory", curr_tid)
        if tdata:
            parent_tid = tdata.get("parent_theory")
            if parent_tid and parent_tid not in target_theories:
                target_theories.add(parent_tid)
                to_visit.append(parent_tid)
    return target_theories


def _validate_create_context_args(
    for_agent_type: str,
    from_exploration: str | None,
    from_literatures: list[str] | None,
    from_theories: list[str] | None,
    from_reviews: list[str] | None,
    from_experiments: list[str] | None,
    from_predictions: list[str] | None,
) -> None:
    if for_agent_type == "write-theory":
        if from_literatures and len(from_literatures) > 1:
            raise ValueError(
                "write-theory accepts at most one --from_literature "
                "(refine-hypothesis, edit-theory and expand-theory support multiple)"
            )
    elif for_agent_type in (
        "falsify-hypothesis",
        "suggest-expansions",
        "polish-theory",
        "streamline-theory",
        "edit-theory",
    ):
        if not from_theories or len(from_theories) != 1:
            raise ValueError(
                f"Exactly one --from_theory is required for {for_agent_type}"
            )
    elif for_agent_type in ("refine-hypothesis", "expand-theory"):
        if not from_theories or len(from_theories) != 1:
            raise ValueError(
                f"Exactly one --from_theory is required for {for_agent_type}"
            )
        if not from_reviews:
            raise ValueError(
                f"At least one --from_review is required for {for_agent_type}"
            )
    elif for_agent_type == "review-theory":
        if not from_theories or len(from_theories) != 1:
            raise ValueError("Exactly one --from_theory is required for review-theory")
    elif for_agent_type == "predict-experiments":
        if not from_theories or len(from_theories) != 1:
            raise ValueError(
                "Exactly one --from_theory is required for predict-experiments"
            )
        if not from_experiments:
            raise ValueError(
                "At least one --from_experiment is required for predict-experiments"
            )
    elif for_agent_type == "rank-predictions":
        if not from_experiments or len(from_experiments) != 1:
            raise ValueError(
                "Exactly one --from_experiment is required for rank-predictions"
            )
        if not from_predictions:
            raise ValueError(
                "At least one --from_prediction is required for rank-predictions"
            )
    elif for_agent_type in ("score-theories", "write-different-theory"):
        if not from_theories:
            raise ValueError(
                f"At least one --from_theory is required for {for_agent_type}"
            )
    elif for_agent_type == "score-soundness":
        if not from_theories or len(from_theories) != 1:
            raise ValueError(
                "Exactly one --from_theory is required for score-soundness"
            )
    elif for_agent_type == "score-length":
        if not from_theories or len(from_theories) != 1:
            raise ValueError("Exactly one --from_theory is required for score-length")
    elif for_agent_type == "rank-explanatory-power":
        if not from_theories:
            raise ValueError(
                f"At least one --from_theory is required for {for_agent_type}"
            )
    else:
        raise ValueError(f"Unknown target agent type {for_agent_type!r}.")


def create_context(
    for_agent_type: str,
    target_folder: Path,
    from_exploration: str | None = None,
    from_literatures: list[str] | None = None,
    from_theories: list[str] | None = None,
    from_reviews: list[str] | None = None,
    from_experiments: list[str] | None = None,
    from_predictions: list[str] | None = None,
) -> None:
    """Assemble upstream artifacts into *target_folder* for the next agent."""
    db_root = get_db_path()

    _validate_create_context_args(
        for_agent_type=for_agent_type,
        from_exploration=from_exploration,
        from_literatures=from_literatures,
        from_theories=from_theories,
        from_reviews=from_reviews,
        from_experiments=from_experiments,
        from_predictions=from_predictions,
    )

    with DatabaseSession(db_root) as session:
        target_folder.mkdir(parents=True, exist_ok=True)

        # 1. Exploration
        if from_exploration:
            if session.get_metadata("exploration", from_exploration):
                copy_artifact(
                    db_root / "exploration" / from_exploration,
                    target_folder / "exploration",
                )
            else:
                raise ValueError(
                    f"Exploration {from_exploration!r} not found or invisible"
                )

        # 2. Literature
        if from_literatures:
            if for_agent_type == "write-theory":
                # Special case: flat literature layout
                copy_artifact(
                    db_root / "literature" / from_literatures[0],
                    target_folder / "literature",
                )
            else:
                lit_root = target_folder / "literature"
                lit_root.mkdir(exist_ok=True)
                for lid in from_literatures:
                    if session.get_metadata("literature", lid):
                        copy_artifact(db_root / "literature" / lid, lit_root / lid)
                    else:
                        raise ValueError(f"Literature {lid!r} not found or invisible")

        # 3. Theories (The dispatch for different layout requirements)
        if from_theories:
            if for_agent_type in (
                "score-theories",
                "rank-explanatory-power",
                "write-different-theory",
            ):
                # Multiple theories in theories/ folder
                theories_root = target_folder / "theories"
                theories_root.mkdir(exist_ok=True)
                for tid in from_theories:
                    copy_artifact(db_root / "theory" / tid, theories_root / tid)
            else:
                # Single theory in theory/ folder
                copy_artifact(
                    db_root / "theory" / from_theories[0], target_folder / "theory"
                )

        # 4. Reviews
        if from_reviews:
            reviews_root = target_folder / "reviews"
            reviews_root.mkdir(exist_ok=True)
            for rid in from_reviews:
                copy_artifact(db_root / "review" / rid, reviews_root / rid)

        # 5. Experiments
        if from_experiments:
            if for_agent_type == "predict-experiments":
                for exp_id in from_experiments:
                    fetch_experiment(target_folder, exp_id, exclude_results=True)
            elif for_agent_type == "rank-predictions":
                copy_artifact(
                    db_root / "experiment" / from_experiments[0],
                    target_folder / "experiment",
                )

        # 6. Predictions
        if from_predictions:
            preds_root = target_folder / "predictions"
            preds_root.mkdir(exist_ok=True)
            for pid in from_predictions:
                copy_artifact(db_root / "prediction" / pid, preds_root / pid)

        # --- Post-processing: Advanced Data Gathering ---

        if for_agent_type == "score-theories":
            # Add up to 30 experiments relevant to the theories being scored
            matched_experiments_by_base: dict[str, list[tuple[str, str]]] = {
                tid: [] for tid in from_theories
            }
            base_ancestors = {
                tid: _get_ancestor_theories(session, [tid]) for tid in from_theories
            }

            for meta_path, data in session.iter_metadata("experiment"):
                parent_theory = data.get("parent_theory")
                if parent_theory:
                    eid = data.get("id")
                    created_at = data.get("created_at", "")
                    for base_tid, ancestors in base_ancestors.items():
                        if parent_theory in ancestors:
                            matched_experiments_by_base[base_tid].append(
                                (created_at, eid)
                            )

            for exps in matched_experiments_by_base.values():
                exps.sort(key=lambda x: x[0], reverse=True)

            selected_eids: set[str] = set()
            pointers = {tid: 0 for tid in from_theories}
            while len(selected_eids) < 30:
                added = False
                for tid in from_theories:
                    exps = matched_experiments_by_base[tid]
                    if pointers[tid] < len(exps):
                        selected_eids.add(exps[pointers[tid]][1])
                        pointers[tid] += 1
                        added = True
                if not added:
                    break

            for eid in selected_eids:
                fetch_experiment(target_folder, eid, exclude_results=True)

        elif for_agent_type == "score-soundness":
            # Add all 'falsify-hypothesis' reviews for the given theory
            reviews_root = target_folder / "reviews"
            reviews_root.mkdir(exist_ok=True)
            tid = from_theories[0]
            for _, data in session.iter_metadata("review"):
                if (
                    data.get("parent_theory") == tid
                    and data.get("agent_type") == "falsify-hypothesis"
                ):
                    copy_artifact(
                        db_root / "review" / data["id"], reviews_root / data["id"]
                    )

        elif for_agent_type == "rank-explanatory-power":
            # Add all 'suggest-expansions' reviews for the theories
            reviews_root = target_folder / "reviews"
            reviews_root.mkdir(exist_ok=True)
            tids = set(from_theories)
            for _, data in session.iter_metadata("review"):
                if (
                    data.get("parent_theory") in tids
                    and data.get("agent_type") == "suggest-expansions"
                ):
                    copy_artifact(
                        db_root / "review" / data["id"], reviews_root / data["id"]
                    )


def fetch_experiment(
    target_folder: Path, experiment_id: str, exclude_results: bool = False
) -> None:
    """Fetch an experiment into an existing context folder under
    ``experiments/<experiment_id>/``.
    """
    db_root = get_db_path()
    with DatabaseSession(db_root) as session:
        if not session.get_metadata("experiment", experiment_id):
            raise ValueError(f"Experiment {experiment_id!r} not found or invisible")

        dst_root = target_folder / "experiments"
        dst_root.mkdir(exist_ok=True)
        copy_artifact(
            db_root / "experiment" / experiment_id,
            dst_root / experiment_id,
            exclude_results=exclude_results,
        )


def search_experiments(
    query: str | None = None,
    tags: list[str] | None = None,
    parent_theory: str | None = None,
    parent_review: str | None = None,
    parent_agent_type: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Search stored experiments by substring match on description + metadata.

    This is intentionally simple (token-presence scoring) — it is meant to
    help callers discover prior experiments relevant to their current task,
    not to replace a real search index. Results are sorted by descending
    score, then by recency.
    """
    db_root = get_db_path()
    tag_filters = [t.strip().lower() for t in (tags or []) if t.strip()]
    query_tokens = [t.lower() for t in (query or "").split() if len(t) >= 3]

    results: list[tuple[int, str, dict]] = []

    with DatabaseSession(db_root) as session:
        for meta_path, data in session.iter_metadata("experiment"):
            extra = data.get("extra") or {}

            if parent_theory and data.get("parent_theory") != parent_theory:
                continue
            if parent_review and extra.get("parent_review") != parent_review:
                continue
            if (
                parent_agent_type
                and extra.get("parent_agent_type") != parent_agent_type
            ):
                continue

            entry_tags = [
                t.strip().lower()
                for t in (extra.get("tags", "").split(",") if extra.get("tags") else [])
                if t.strip()
            ]
            if tag_filters and not all(t in entry_tags for t in tag_filters):
                continue

            description = ""
            desc_path = meta_path.parent / "description.md"
            if desc_path.is_file():
                try:
                    description = desc_path.read_text().lower()
                except OSError:
                    description = ""

            if query_tokens:
                score = sum(1 for tok in query_tokens if tok in description)
                score += sum(1 for tok in query_tokens if tok in " ".join(entry_tags))
                if score == 0:
                    continue
            else:
                score = 0

            # include a short preview to help the caller skim results
            preview = ""
            if desc_path.is_file():
                try:
                    raw = desc_path.read_text()
                    preview = " ".join(raw.split())[:240]
                except OSError:
                    preview = ""
            data["preview"] = preview
            results.append((score, data.get("created_at", ""), data))

    results.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [d for _, _, d in results[:limit]]


def fetch_literature(target_folder: Path, literature_id: str) -> None:
    """Fetch a literature review into an existing context folder under
    ``literature/<literature_id>/``.
    """
    db_root = get_db_path()
    with DatabaseSession(db_root) as session:
        if not session.get_metadata("literature", literature_id):
            raise ValueError(
                f"Literature review {literature_id!r} not found or invisible"
            )

        dst_root = target_folder / "literature"
        dst_root.mkdir(exist_ok=True)
        copy_artifact(db_root / "literature" / literature_id, dst_root / literature_id)


def list_entries(
    entry_type: str, parent_theory: str | None = None, sort_by: str = "created_at"
) -> list[dict]:
    """List stored entries of the given type."""
    if entry_type not in VALID_CATEGORIES:
        raise ValueError(
            f"Unknown entry type {entry_type!r}. Must be one of: "
            f"{', '.join(VALID_CATEGORIES)}"
        )
    if sort_by not in ("created_at", "score"):
        raise ValueError(
            f"Unknown sort_by {sort_by!r}. Must be 'created_at' or 'score'"
        )
    if sort_by == "score" and entry_type != "theory":
        raise ValueError("Sorting by score is only supported for entry_type 'theory'")

    db_root = get_db_path()

    results: list[dict] = []

    with DatabaseSession(db_root) as session:
        for _, data in session.iter_metadata(entry_type):
            if (
                entry_type in ("review", "experiment")
                and parent_theory
                and data.get("parent_theory") != parent_theory
            ):
                continue
            results.append(data)

        if sort_by == "created_at":
            results.sort(key=lambda d: d.get("created_at", ""))
        elif sort_by == "score":
            population = session.get_population()
            scores = {}
            subscores = {}
            if population:
                leaf_map = {}
                for organism, eval_result in population.organisms:
                    if hasattr(organism, "theory_id"):
                        theory_id = organism.theory_id
                        scores[theory_id] = eval_result.score
                        subscores[theory_id] = (
                            eval_result.subscores
                            if hasattr(eval_result, "subscores")
                            else {}
                        )
                        leaf_map[theory_id] = (
                            len(population.get_children(organism)) == 0
                        )

            for d in results:
                tid = d.get("id")
                d["score"] = scores.get(tid)
                d["subscores"] = subscores.get(tid)
                d["is_leaf_node"] = leaf_map.get(tid, False) if population else False

            results.sort(
                key=lambda d: (
                    (d.get("score") if d.get("score") is not None else float("-inf")),
                    d.get("created_at", ""),
                )
            )

    return results


def sample_theories(
    num_theories: int, purpose: Literal["scoring", "mutation"]
) -> list[dict]:
    db_root = get_db_path()
    with DatabaseSession(db_root) as session:
        population = session.get_population()
        if not population:
            return []
        if purpose == "scoring":
            samples = population.sample_parents(
                k=min(
                    len(
                        [
                            o
                            for o, r in population.organisms
                            if r.trainable_failure_cases
                        ]
                    ),
                    num_theories,
                ),
                replace=False,
                novelty_weight=0.0,
            )
        elif purpose == "mutation":
            samples = population.sample_parents(k=num_theories)
        else:
            raise ValueError(f"Unknown sampling purpose {purpose!r}")

        return [
            {
                "id": o.theory_id,
                "score": r.score,
                "subscores": r.subscores if hasattr(r, "subscores") else {},
            }
            for o, r in samples
        ]


def rescore_theories(theory_scores: dict[str, dict[str, float]]) -> None:
    db_root = get_db_path()
    with DatabaseSession(db_root) as session:
        population = session.get_population()
        if not population:
            raise RuntimeError("Population is empty; cannot rescore theories")

        # Step 1: Update scores for the provided theories
        updated_theories = set()
        for organism, eval_result in population.organisms:
            if organism.theory_id in theory_scores:
                theory_score = theory_scores[organism.theory_id]
                if "score" not in theory_score:
                    raise ValueError(
                        f"Missing 'score' for theory ID {organism.theory_id!r} in input"
                    )
                eval_result.score = theory_score["score"]
                eval_result.subscores = theory_score
                updated_theories.add(organism.theory_id)

        if set(theory_scores.keys()) - updated_theories:
            raise ValueError(
                f"Theory IDs not found in population: "
                f"{set(theory_scores.keys()) - updated_theories}"
            )

        # Step 2: Decay the scores of all remaining organisms
        for organism, score in population.organisms:
            if organism.theory_id not in updated_theories:
                score.score *= SCORE_DECAY_RATE

        session.mark_population_modified()


def commit_transaction(transaction_id: str) -> None:
    """Commit a transaction by finalizing staged objects and adding to population."""
    db_root = get_db_path()
    with DatabaseSession(db_root) as session:
        staged_items = []
        for meta_path, data in session.iter_all_metadata(include_uncommitted=True):
            if data.get("staged_for_transaction") == transaction_id:
                staged_items.append((meta_path, data))

        if not staged_items:
            return

        # 1. Unstage everything
        for meta_path, data in staged_items:
            del data["staged_for_transaction"]

            if MAKE_READONLY:
                os.chmod(meta_path, os.stat(meta_path).st_mode | stat.S_IWUSR)

            meta_path.write_text(json.dumps(data, indent=2) + "\n")

            if MAKE_READONLY:
                os.chmod(
                    meta_path,
                    os.stat(meta_path).st_mode
                    & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH),
                )

        # 2. Update population (Theories first, sorted by created_at)
        theories = [d for _, d in staged_items if d.get("category") == "theory"]
        theories.sort(key=lambda d: d.get("created_at", ""))
        for t in theories:
            try:
                session.record_theory(
                    theory_id=t.get("id"),
                    parent_theory_id=t.get("parent_theory"),
                )
            except Exception as e:
                print(f"Error recording theory {t.get('id')!r} in population: {e}")

        # 3. Update population (Reviews)
        reviews = [d for _, d in staged_items if d.get("category") == "review"]
        for r in reviews:
            try:
                session.record_review(
                    theory_id=r.get("parent_theory"),
                    review_id=r.get("id"),
                )
            except Exception as e:
                print(f"Error recording review {r.get('id')!r} in population: {e}")


def export_theory_population(dest_path: Path) -> None:
    """Export the theory population to a single-line JSON file."""
    db_root = get_db_path()
    with DatabaseSession(db_root) as session:
        population = session.get_population()
        if not population:
            raise RuntimeError("Population is empty; cannot export")

        data = population.log_to_json_dict()
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    db_root = get_db_path(ensure_exists=False)
    if db_root.exists():
        with DatabaseSession(db_root):
            log_path = db_root / "access.log"
            actual_argv = sys.argv if argv is None else [sys.argv[0]] + argv
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(
                    f"[{datetime.now(timezone.utc).isoformat()}] cwd={Path.cwd()} argv={actual_argv}\n"
                )

    parser = argparse.ArgumentParser(
        prog="context_manager",
        description="Agent Context Manager — store, assemble, and list pipeline artifacts.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- init ----------------------------------------------------------------
    sub.add_parser("init", help="Initialize a new database")

    # -- store_results -------------------------------------------------------
    sp_store = sub.add_parser(
        "store_results", help="Persist agent output into the database"
    )
    sp_store.add_argument(
        "--from_agent_type",
        required=True,
        choices=list(AGENT_TYPE_MAP.keys()),
        help="Type of agent that produced the output",
    )
    sp_store.add_argument(
        "--from_folder",
        required=True,
        type=Path,
        help="Path to folder containing agent output",
    )
    sp_store.add_argument(
        "--parent_theory",
        default=None,
        help="Parent theory ID (required for falsify-hypothesis)",
    )
    sp_store.add_argument(
        "--metadata",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Extra metadata key-value pair (repeatable)",
    )

    # -- create_context ------------------------------------------------------
    sp_ctx = sub.add_parser(
        "create_context", help="Assemble context for the next agent"
    )
    sp_ctx.add_argument(
        "--for_agent_type",
        required=True,
        choices=[
            "write-theory",
            "falsify-hypothesis",
            "refine-hypothesis",
            "review-theory",
            "suggest-expansions",
            "expand-theory",
            "edit-theory",
            "predict-experiments",
            "rank-predictions",
            "score-theories",
            "score-soundness",
            "score-length",
            "rank-explanatory-power",
            "polish-theory",
            "streamline-theory",
            "search-literature",
            "write-different-theory",
        ],
        help="Type of agent to prepare context for",
    )
    sp_ctx.add_argument(
        "--target_folder",
        required=True,
        type=Path,
        help="Folder to populate with upstream artifacts",
    )
    sp_ctx.add_argument("--from_exploration", default=None, help="Exploration ID")
    sp_ctx.add_argument(
        "--from_literature",
        action="append",
        default=[],
        dest="from_literatures",
        help=(
            "Literature review ID. Repeatable for refine-hypothesis, edit-theory, and "
            "expand-theory (each lands in literature/<L_ID>/); write-theory "
            "accepts at most one and uses a flat literature/ layout."
        ),
    )
    sp_ctx.add_argument(
        "--from_theory",
        action="append",
        default=[],
        dest="from_theories",
        help="Theory ID (repeatable)",
    )
    sp_ctx.add_argument(
        "--from_review",
        action="append",
        default=[],
        dest="from_reviews",
        help="Review ID (repeatable)",
    )
    sp_ctx.add_argument(
        "--from_experiment",
        action="append",
        default=[],
        dest="from_experiments",
        help="Experiment ID (repeatable, used by predict-experiments)",
    )
    sp_ctx.add_argument(
        "--from_prediction",
        action="append",
        default=[],
        dest="from_predictions",
        help="Prediction ID (repeatable, used by rank-predictions)",
    )

    # -- fetch_literature ----------------------------------------------------
    sp_fetch_lit = sub.add_parser(
        "fetch_literature",
        help="Fetch a literature review into an existing context folder.",
    )
    sp_fetch_lit.add_argument(
        "--target_folder",
        required=True,
        type=Path,
        help="Existing context folder produced by a prior create_context call",
    )
    sp_fetch_lit.add_argument(
        "--from_literature",
        required=True,
        help="Literature review ID to add (nested under literature/<L_ID>/)",
    )

    # -- fetch_experiment ----------------------------------------------------
    sp_fetch_exp = sub.add_parser(
        "fetch_experiment",
        help="Fetch an experiment into an existing context folder.",
    )
    sp_fetch_exp.add_argument(
        "--target_folder",
        required=True,
        type=Path,
        help="Existing context folder produced by a prior create_context call",
    )
    sp_fetch_exp.add_argument(
        "--from_experiment",
        required=True,
        help="Experiment ID to add (nested under experiments/<X_ID>/)",
    )
    sp_fetch_exp.add_argument(
        "--exclude_results",
        action="store_true",
        help="Exclude experiment results (only fetch description and script)",
    )

    # -- search_experiments --------------------------------------------------
    sp_search_exp = sub.add_parser(
        "search_experiments",
        help=(
            "Search stored experiments by substring match on description "
            "and tags. Returns matching experiment IDs with short previews."
        ),
    )
    sp_search_exp.add_argument(
        "--query",
        default=None,
        help="Free-text query (tokens >=3 chars are matched against description + tags)",
    )
    sp_search_exp.add_argument(
        "--tag",
        action="append",
        default=[],
        dest="tags",
        help="Require a specific tag on the experiment (repeatable)",
    )
    sp_search_exp.add_argument(
        "--parent_theory",
        default=None,
        help="Filter to experiments run in support of a specific theory",
    )
    sp_search_exp.add_argument(
        "--parent_review",
        default=None,
        help="Filter to experiments run in support of a specific review",
    )
    sp_search_exp.add_argument(
        "--parent_agent_type",
        default=None,
        help="Filter to experiments invoked by a specific agent type",
    )
    sp_search_exp.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of results to return",
    )
    sp_search_exp.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON instead of a table",
    )

    # -- commit --------------------------------------------------------------
    sp_commit = sub.add_parser(
        "commit", help="Commit a transaction, finalizing staged objects"
    )
    sp_commit.add_argument("transaction_id", help="The transaction ID to commit")

    # -- list ----------------------------------------------------------------
    sp_list = sub.add_parser("list", help="List stored entries")
    sp_list.add_argument(
        "--type",
        required=True,
        choices=list(VALID_CATEGORIES),
        dest="entry_type",
        help="Type of entries to list",
    )
    sp_list.add_argument(
        "--parent_theory",
        default=None,
        help="Filter reviews by parent theory ID",
    )
    sp_list.add_argument(
        "--sort_by",
        choices=["created_at", "score"],
        default="created_at",
        help="Sort list by property (score is only supported for theory entries)",
    )
    sp_list.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON instead of a table",
    )

    # -- sample --------------------------------------------------------------
    sp_sample = sub.add_parser(
        "sample_theories", help="Sample theory IDs from the population"
    )
    sp_sample.add_argument(
        "--num_theories",
        type=int,
        required=True,
        help="Number of theory IDs to sample",
    )
    sp_sample.add_argument(
        "--purpose",
        choices=["scoring", "mutation"],
        required=True,
        help="Intended use of the sampled theories (may influence sampling strategy)",
    )
    sp_sample.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON instead of a table",
    )

    # -- rescore ----------------------------------------------------------------
    sp_rescore = sub.add_parser(
        "rescore_theories", help="Submit updated scores for theories"
    )
    sp_rescore.add_argument(
        "theory_score_dict",
        help='Dictionary of theory IDs and their updated scores as a JSON object string (e.g. \'{"theory_id_1": {"score": 0.8, "subscore_1": 0.5, "subscore_2": 0.3}, "theory_id_2": {"score": 0.3, "subscore_1": 0.2, "subscore_2": 0.1} }\'). The score object for each theory must contain at least the `score` field for its overall score.',
    )

    # -- export_theory_population --------------------------------------------
    sp_export = sub.add_parser(
        "export_theory_population", help="Export theory population to a JSON file"
    )
    sp_export.add_argument(
        "dest_file",
        type=Path,
        help="Destination .json file",
    )

    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            db_path = get_db_path(ensure_exists=False)
            if db_path.exists():
                print(
                    f"Database path already exists: {db_path}. Initialization not needed."
                )
                return
            db_path.mkdir(parents=True)
            print(f"Initialized database at {db_path}")

        elif args.command == "store_results":
            extra: dict[str, str] = {}
            for item in args.metadata:
                if "=" not in item:
                    raise ValueError(
                        f"Invalid --metadata format {item!r}: expected KEY=VALUE"
                    )
                k, v = item.split("=", 1)
                extra[k] = v

            new_id = store_results(
                from_agent_type=args.from_agent_type,
                from_folder=args.from_folder.resolve(),
                parent_theory=args.parent_theory,
                metadata_extra=extra,
            )
            print(f"Result stored with ID: {new_id}")

        elif args.command == "create_context":
            create_context(
                for_agent_type=args.for_agent_type,
                target_folder=args.target_folder.resolve(),
                from_exploration=args.from_exploration,
                from_literatures=args.from_literatures or None,
                from_theories=args.from_theories or None,
                from_reviews=args.from_reviews or None,
                from_experiments=args.from_experiments or None,
                from_predictions=args.from_predictions or None,
            )

        elif args.command == "fetch_literature":
            fetch_literature(
                target_folder=args.target_folder.resolve(),
                literature_id=args.from_literature,
            )

        elif args.command == "fetch_experiment":
            fetch_experiment(
                target_folder=args.target_folder.resolve(),
                experiment_id=args.from_experiment,
                exclude_results=args.exclude_results,
            )

        elif args.command == "search_experiments":
            hits = search_experiments(
                query=args.query,
                tags=args.tags or None,
                parent_theory=args.parent_theory,
                parent_review=args.parent_review,
                parent_agent_type=args.parent_agent_type,
                limit=args.limit,
            )
            if args.json_output:
                print(json.dumps(hits, indent=2))
            else:
                if not hits:
                    print("No matching experiments found.")
                else:
                    print(f"{'ID':<40} {'Created At':<28} {'Parent Theory':<40}")
                    print("-" * 108)
                    for h in hits:
                        print(
                            f"{h.get('id', '?'):<40} "
                            f"{h.get('created_at', '?'):<28} "
                            f"{(h.get('parent_theory') or '-'):<40}"
                        )
                        preview = h.get("preview")
                        if preview:
                            print(f"  {preview}")

        elif args.command == "commit":
            commit_transaction(args.transaction_id)

        elif args.command == "list":
            entries = list_entries(
                args.entry_type,
                parent_theory=getattr(args, "parent_theory", None),
                sort_by=args.sort_by,
            )
            if args.json_output:
                print(json.dumps(entries, indent=2))
            else:
                if not entries:
                    print(f"No {args.entry_type} entries found.")
                else:
                    if args.sort_by == "score":
                        subscore_keys = set()
                        for e in entries:
                            subscore_keys.update(
                                e.get("subscores", {}).keys()
                                if e.get("subscores")
                                else []
                            )
                        subscore_keys = sorted(list(subscore_keys))

                        header = f"{'ID':<40} {'Score':<20} {'Created At':<28} {'Agent Type':<20}"
                        for k in subscore_keys:
                            header += f" {k.capitalize():<20}"
                        print(header)
                        print("-" * len(header))
                        for e in entries:
                            score_val = e.get("score")
                            score_str = (
                                f"{score_val:.4f}"
                                if isinstance(score_val, float)
                                else "N/A"
                            )
                            row = f"{e.get('id', '?'):<40} {score_str:<20} {e.get('created_at', '?'):<28} {e.get('agent_type', '?'):<20}"
                            for k in subscore_keys:
                                val = (
                                    e.get("subscores", {}).get(k)
                                    if e.get("subscores")
                                    else None
                                )
                                val_str = (
                                    f"{val:.4f}"
                                    if isinstance(val, (int, float))
                                    else str(val)
                                    if val is not None
                                    else "N/A"
                                )
                                row += f" {val_str:<20}"
                            print(row)
                    else:
                        print(f"{'ID':<40} {'Created At':<28} {'Agent Type':<20}")
                        print("-" * 88)
                        for e in entries:
                            print(
                                f"{e.get('id', '?'):<40} "
                                f"{e.get('created_at', '?'):<28} "
                                f"{e.get('agent_type', '?'):<20}"
                            )

        elif args.command == "sample_theories":
            sampled_theories = sample_theories(
                num_theories=args.num_theories, purpose=args.purpose
            )
            if getattr(args, "json_output", False):
                print(json.dumps(sampled_theories, indent=2))
            else:
                if not sampled_theories:
                    print("No theories sampled.")
                else:
                    # build headers based on dynamic subscores
                    subscore_keys = set()
                    for t in sampled_theories:
                        subscore_keys.update(t.get("subscores", {}).keys())
                    subscore_keys = sorted(list(subscore_keys))

                    header = f"{'ID':<40} {'Score':<20}"
                    for k in subscore_keys:
                        header += f" {k.capitalize():<20}"
                    print(header)
                    print("-" * len(header))
                    for t in sampled_theories:
                        row = f"{t['id']:<40} {t['score']:<20.4f}"
                        for k in subscore_keys:
                            val = t.get("subscores", {}).get(k)
                            val_str = (
                                f"{val:.4f}"
                                if isinstance(val, (int, float))
                                else str(val)
                                if val is not None
                                else "N/A"
                            )
                            row += f" {val_str:<20}"
                        print(row)

        elif args.command == "rescore_theories":
            theory_score_dict = json.loads(args.theory_score_dict)
            if not isinstance(theory_score_dict, dict):
                raise ValueError(
                    "theory_score_dict must be a JSON object mapping theory IDs to scores"
                )
            rescore_theories(theory_score_dict)

        elif args.command == "export_theory_population":
            export_theory_population(args.dest_file)

    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
