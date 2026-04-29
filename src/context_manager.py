"""Agent Context Manager — filesystem-based persistence and context assembly for the Skills pipeline.

Run with ``--help`` to see the available CLI subcommands.
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

from pydantic import BaseModel, ConfigDict, Field

from darwinian_evolver.population import Population, WeightedSamplingPopulation
from darwinian_evolver.problem import (
    EvaluationResult,
    Organism,
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
INITIAL_ROOT_SCORE = 0.5
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
    parent_theory: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)


class TheoryOrganism(Organism):
    """An organism that wraps a single theory artifact in the context_manager DB."""

    theory_id: str = Field(
        description="Theory ID (e.g. 'T_20260414_143100_d4e5f6') stored in the context_manager DB."
    )


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
    return Population.from_snapshot(path.read_bytes())


def _record_theory_in_population(
    db_root: Path, theory_id: str, parent_theory_id: str | None
) -> None:
    """Add a newly-stored theory to population.json, initializing the file if needed.

    Score policy: parentless theories get ``INITIAL_ROOT_SCORE``; theories
    with a parent inherit the parent's current score. (This is a placeholder
    heuristic — will be revisited.)
    """
    path = _population_path(db_root)
    population = _load_population(path)

    if population is None:
        if parent_theory_id is not None:
            raise RuntimeError(
                f"Attempting to record child theory {theory_id!r} with parent "
                f"{parent_theory_id!r} but no population exists yet. The parent "
                f"theory must have been stored before the child."
            )
        organism = TheoryOrganism(theory_id=theory_id)
        result = TheoryEvaluationResult(
            score=INITIAL_ROOT_SCORE, trainable_failure_cases=[]
        )
        population = WeightedSamplingPopulation(
            organism,
            result,
            # Since our scores are largely based on ranking and hence will naturally be centered, we use a fixed midpoint.
            fixed_midpoint_score=0.5,
            sharpness=10.0,
        )
        _save_population(population, path)
        return

    parent_org: TheoryOrganism | None = None
    parent_score: float | None = None
    if parent_theory_id is not None:
        found = _find_organism_by_theory_id(population, parent_theory_id)
        if found is None:
            raise RuntimeError(
                f"Parent theory {parent_theory_id!r} is not in the population; "
                f"refusing to add child {theory_id!r}"
            )
        parent_org, parent_result = found
        parent_score = parent_result.score

    # Inherit an interim score from the parent - typically, organisms will be rescored later.
    score = parent_score if parent_score is not None else INITIAL_ROOT_SCORE
    organism = TheoryOrganism(theory_id=theory_id, parent=parent_org)
    result = TheoryEvaluationResult(score=score, trainable_failure_cases=[])
    population.add(organism, result)
    _save_population(population, path)


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

    with DatabaseLock(db_root):
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

        # --- write metadata ---
        meta = StoredMetadata(
            id=new_id,
            agent_type=from_agent_type,
            category=category,
            created_at=datetime.now(timezone.utc).isoformat(),
            parent_theory=parent_theory
            if from_agent_type in parent_theory_allowed_agents
            else None,
            extra=metadata_extra or {},
        )
        (target_dir / "metadata.json").write_text(
            json.dumps(meta.model_dump(), indent=2) + "\n"
        )

        # --- make immutable ---
        _make_readonly(target_dir)

        # --- add to the theory population ---
        if category == "theory":
            _record_theory_in_population(
                db_root=db_root,
                theory_id=new_id,
                parent_theory_id=parent_theory,
            )

    return new_id


def _get_ancestor_theories(db_root: Path, base_theories: list[str]) -> set[str]:
    """Recursively collect the given theories and all of their ancestors."""
    target_theories = set(base_theories)
    to_visit = list(target_theories)
    while to_visit:
        curr_tid = to_visit.pop()
        curr_meta_path = db_root / "theory" / curr_tid / "metadata.json"
        if curr_meta_path.is_file():
            try:
                tdata = json.loads(curr_meta_path.read_text())
                parent_tid = tdata.get("parent_theory")
                if parent_tid and parent_tid not in target_theories:
                    target_theories.add(parent_tid)
                    to_visit.append(parent_tid)
            except (json.JSONDecodeError, OSError):
                pass
    return target_theories


def _assemble_write_theory(
    target_folder: Path,
    exploration_dir: Path | None,
    literature_dirs: list[tuple[str, Path]],
) -> None:
    dst = target_folder / "exploration"
    shutil.copytree(
        exploration_dir,  # type: ignore[possibly-undefined]
        dst,
        ignore=IGNORE_METADATA_PATTERN,
    )
    _make_writable(dst)
    if literature_dirs:
        _, lit_dir = literature_dirs[0]
        ldst = target_folder / "literature"
        shutil.copytree(lit_dir, ldst, ignore=IGNORE_METADATA_PATTERN)
        _make_writable(ldst)


def _assemble_theory_copy(
    target_folder: Path, theory_dirs: list[tuple[str, Path]]
) -> None:
    dst = target_folder / "theory"
    shutil.copytree(
        theory_dirs[0][1],
        dst,
        ignore=IGNORE_METADATA_PATTERN,
    )
    _make_writable(dst)


def _assemble_refine_expand(
    db_root: Path,
    target_folder: Path,
    theory_dirs: list[tuple[str, Path]],
    from_reviews: list[str] | None,
    literature_dirs: list[tuple[str, Path]],
) -> None:
    dst = target_folder / "theory"
    shutil.copytree(
        theory_dirs[0][1],
        dst,
        ignore=IGNORE_METADATA_PATTERN,
    )
    _make_writable(dst)
    reviews_root = target_folder / "reviews"
    reviews_root.mkdir(exist_ok=True)
    for rid in from_reviews:  # type: ignore[union-attr]
        src = db_root / "review" / rid
        rdst = reviews_root / rid
        shutil.copytree(src, rdst, ignore=IGNORE_METADATA_PATTERN)
        _make_writable(rdst)
    if literature_dirs:
        lit_root = target_folder / "literature"
        lit_root.mkdir(exist_ok=True)
        for lid, lit_dir in literature_dirs:
            ldst = lit_root / lid
            shutil.copytree(lit_dir, ldst, ignore=IGNORE_METADATA_PATTERN)
            _make_writable(ldst)


def _assemble_review_theory(
    target_folder: Path, theory_dirs: list[tuple[str, Path]]
) -> None:
    dst = target_folder / "theory.md"
    src_theory_md = theory_dirs[0][1] / "theory.md"
    if src_theory_md.exists():
        shutil.copy2(src_theory_md, dst)
        _make_writable(dst)


def _assemble_predict_experiments(
    target_folder: Path,
    theory_dirs: list[tuple[str, Path]],
    from_experiments: list[str] | None,
) -> None:
    dst = target_folder / "theory"
    shutil.copytree(
        theory_dirs[0][1],
        dst,
        ignore=IGNORE_METADATA_PATTERN,
    )
    _make_writable(dst)
    for exp_id in from_experiments:  # type: ignore[union-attr]
        fetch_experiment(target_folder, exp_id, exclude_results=True)


def _assemble_rank_predictions(
    db_root: Path,
    target_folder: Path,
    from_predictions: list[str] | None,
    from_experiments: list[str] | None,
) -> None:
    preds_root = target_folder / "predictions"
    preds_root.mkdir(exist_ok=True)
    for pid in from_predictions:  # type: ignore[union-attr]
        src = db_root / "prediction" / pid
        pdst = preds_root / pid
        shutil.copytree(src, pdst, ignore=IGNORE_METADATA_PATTERN)
        _make_writable(pdst)

    exp_id = from_experiments[0]  # type: ignore[index]
    exp_src = db_root / "experiment" / exp_id
    exp_dst = target_folder / "experiment"
    shutil.copytree(exp_src, exp_dst, ignore=IGNORE_METADATA_PATTERN)
    _make_writable(exp_dst)


def _assemble_score_theories(
    db_root: Path,
    target_folder: Path,
    theory_dirs: list[tuple[str, Path]],
    from_theories: list[str] | None,
) -> None:
    theories_root = target_folder / "theories"
    theories_root.mkdir(exist_ok=True)
    for tid, tdir in theory_dirs:
        dst = theories_root / tid
        shutil.copytree(tdir, dst, ignore=IGNORE_METADATA_PATTERN)
        _make_writable(dst)

    matched_experiments_by_base: dict[str, list[tuple[str, str]]] = {
        tid: [] for tid in (from_theories or [])
    }
    exp_root = db_root / "experiment"
    if exp_root.is_dir() and from_theories:
        base_ancestors = {
            tid: _get_ancestor_theories(db_root, [tid]) for tid in from_theories
        }
        for meta_path in exp_root.glob("*/metadata.json"):
            try:
                data = json.loads(meta_path.read_text())
                parent_theory = data.get("parent_theory")
                if parent_theory:
                    eid = data.get("id")
                    created_at = data.get("created_at", "")
                    if eid:
                        for base_tid, ancestors in base_ancestors.items():
                            if parent_theory in ancestors:
                                matched_experiments_by_base[base_tid].append(
                                    (created_at, eid)
                                )
            except (json.JSONDecodeError, OSError):
                continue

    for exps in matched_experiments_by_base.values():
        exps.sort(key=lambda x: x[0], reverse=True)

    num_experiments_to_include = 30
    selected_eids: set[str] = set()

    if from_theories:
        pointers = {tid: 0 for tid in from_theories}
        while len(selected_eids) < num_experiments_to_include:
            added_in_round = False
            for tid in from_theories:
                exps = matched_experiments_by_base[tid]
                while pointers[tid] < len(exps):
                    _, eid = exps[pointers[tid]]
                    pointers[tid] += 1
                    if eid not in selected_eids:
                        selected_eids.add(eid)
                        added_in_round = True
                        break
                if len(selected_eids) >= num_experiments_to_include:
                    break
            if not added_in_round:
                break

    for exp_id in selected_eids:
        fetch_experiment(target_folder, exp_id, exclude_results=True)


def _assemble_score_soundness(
    db_root: Path, target_folder: Path, theory_dirs: list[tuple[str, Path]]
) -> None:
    dst = target_folder / "theory"
    shutil.copytree(
        theory_dirs[0][1],
        dst,
        ignore=IGNORE_METADATA_PATTERN,
    )
    _make_writable(dst)

    reviews_root = target_folder / "reviews"
    reviews_root.mkdir(exist_ok=True)
    review_root_dir = db_root / "review"
    tid = theory_dirs[0][0]
    if review_root_dir.is_dir():
        for meta_path in sorted(review_root_dir.glob("*/metadata.json")):
            try:
                data = json.loads(meta_path.read_text())
                if (
                    data.get("parent_theory") == tid
                    and data.get("agent_type") == "falsify-hypothesis"
                ):
                    rid = data.get("id")
                    if rid:
                        src_review = review_root_dir / rid
                        rdst = reviews_root / rid
                        shutil.copytree(
                            src_review, rdst, ignore=IGNORE_METADATA_PATTERN
                        )
                        _make_writable(rdst)
            except (json.JSONDecodeError, OSError):
                continue


def _assemble_rank_predictive_power(
    db_root: Path,
    target_folder: Path,
    theory_dirs: list[tuple[str, Path]],
    from_theories: list[str] | None,
) -> None:
    theories_root = target_folder / "theories"
    theories_root.mkdir(exist_ok=True)
    for tid, tdir in theory_dirs:
        dst = theories_root / tid
        shutil.copytree(tdir, dst, ignore=IGNORE_METADATA_PATTERN)
        _make_writable(dst)

    reviews_root = target_folder / "reviews"
    reviews_root.mkdir(exist_ok=True)
    review_root_dir = db_root / "review"
    if review_root_dir.is_dir():
        for meta_path in sorted(review_root_dir.glob("*/metadata.json")):
            try:
                data = json.loads(meta_path.read_text())
                if (
                    data.get("parent_theory") in from_theories
                    and data.get("agent_type") == "suggest-expansions"
                ):
                    rid = data.get("id")
                    if rid:
                        src_review = review_root_dir / rid
                        rdst = reviews_root / rid
                        shutil.copytree(
                            src_review, rdst, ignore=IGNORE_METADATA_PATTERN
                        )
                        _make_writable(rdst)
            except (json.JSONDecodeError, OSError):
                continue


def _resolve_context_paths(
    db_root: Path,
    from_exploration: str | None,
    from_literatures: list[str] | None,
    from_theories: list[str] | None,
    from_reviews: list[str] | None,
    from_predictions: list[str] | None,
) -> tuple[Path | None, list[tuple[str, Path]], list[tuple[str, Path]]]:
    exploration_dir = None
    if from_exploration:
        exploration_dir = db_root / "exploration" / from_exploration
        if not exploration_dir.is_dir():
            raise ValueError(
                f"Exploration {from_exploration!r} not found in database "
                f"(expected {exploration_dir})"
            )

    literature_dirs: list[tuple[str, Path]] = []
    if from_literatures:
        for lid in from_literatures:
            lit_dir = db_root / "literature" / lid
            if not lit_dir.is_dir():
                raise ValueError(
                    f"Literature review {lid!r} not found in database "
                    f"(expected {lit_dir})"
                )
            literature_dirs.append((lid, lit_dir))

    theory_dirs: list[tuple[str, Path]] = []
    if from_theories:
        for tid in from_theories:
            theory_dir = db_root / "theory" / tid
            if not theory_dir.is_dir():
                raise ValueError(
                    f"Theory {tid!r} not found in database (expected {theory_dir})"
                )
            theory_dirs.append((tid, theory_dir))

    if from_reviews:
        for rid in from_reviews:
            review_dir = db_root / "review" / rid
            if not review_dir.is_dir():
                raise ValueError(
                    f"Review {rid!r} not found in database (expected {review_dir})"
                )

    if from_predictions:
        for pid in from_predictions:
            pred_dir = db_root / "prediction" / pid
            if not pred_dir.is_dir():
                raise ValueError(
                    f"Prediction {pid!r} not found in database (expected {pred_dir})"
                )

    return exploration_dir, literature_dirs, theory_dirs


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
        if not from_exploration:
            raise ValueError("--from_exploration is required for write-theory")
        if from_literatures and len(from_literatures) > 1:
            raise ValueError(
                "write-theory accepts at most one --from_literature "
                "(refine-hypothesis and expand-theory support multiple)"
            )
    elif for_agent_type in (
        "falsify-hypothesis",
        "suggest-expansions",
        "polish-theory",
        "streamline-theory",
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
    elif for_agent_type == "score-theories":
        if not from_theories:
            raise ValueError(
                f"At least one --from_theory is required for {for_agent_type}"
            )
    elif for_agent_type == "score-soundness":
        if not from_theories or len(from_theories) != 1:
            raise ValueError(
                "Exactly one --from_theory is required for score-soundness"
            )
    elif for_agent_type == "rank-predictive-power":
        if not from_theories:
            raise ValueError(
                f"At least one --from_theory is required for {for_agent_type}"
            )
    else:
        raise ValueError(
            f"Unknown target agent type {for_agent_type!r}. "
            f"Must be one of: write-theory, falsify-hypothesis, refine-hypothesis, "
            f"review-theory, suggest-expansions, expand-theory, "
            f"predict-experiments, rank-predictions, score-theories, score-soundness, "
            f"rank-predictive-power"
        )


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

    # --- validate required references per agent type ---
    _validate_create_context_args(
        for_agent_type=for_agent_type,
        from_exploration=from_exploration,
        from_literatures=from_literatures,
        from_theories=from_theories,
        from_reviews=from_reviews,
        from_experiments=from_experiments,
        from_predictions=from_predictions,
    )

    with DatabaseLock(db_root):
        # --- resolve and validate paths ---
        exploration_dir, literature_dirs, theory_dirs = _resolve_context_paths(
            db_root=db_root,
            from_exploration=from_exploration,
            from_literatures=from_literatures,
            from_theories=from_theories,
            from_reviews=from_reviews,
            from_predictions=from_predictions,
        )

        # --- create target and copy ---
        target_folder.mkdir(parents=True, exist_ok=True)

        if for_agent_type == "write-theory":
            _assemble_write_theory(
                target_folder=target_folder,
                exploration_dir=exploration_dir,
                literature_dirs=literature_dirs,
            )

        elif for_agent_type in (
            "falsify-hypothesis",
            "suggest-expansions",
            "polish-theory",
            "streamline-theory",
        ):
            _assemble_theory_copy(target_folder=target_folder, theory_dirs=theory_dirs)

        elif for_agent_type in ("refine-hypothesis", "expand-theory"):
            _assemble_refine_expand(
                db_root=db_root,
                target_folder=target_folder,
                theory_dirs=theory_dirs,
                from_reviews=from_reviews,
                literature_dirs=literature_dirs,
            )

        elif for_agent_type == "review-theory":
            _assemble_review_theory(
                target_folder=target_folder, theory_dirs=theory_dirs
            )

        elif for_agent_type == "predict-experiments":
            _assemble_predict_experiments(
                target_folder=target_folder,
                theory_dirs=theory_dirs,
                from_experiments=from_experiments,
            )

        elif for_agent_type == "rank-predictions":
            _assemble_rank_predictions(
                db_root=db_root,
                target_folder=target_folder,
                from_predictions=from_predictions,
                from_experiments=from_experiments,
            )

        elif for_agent_type == "score-theories":
            _assemble_score_theories(
                db_root=db_root,
                target_folder=target_folder,
                theory_dirs=theory_dirs,
                from_theories=from_theories,
            )

        elif for_agent_type == "score-soundness":
            _assemble_score_soundness(
                db_root=db_root,
                target_folder=target_folder,
                theory_dirs=theory_dirs,
            )

        elif for_agent_type == "rank-predictive-power":
            _assemble_rank_predictive_power(
                db_root=db_root,
                target_folder=target_folder,
                theory_dirs=theory_dirs,
                from_theories=from_theories,
            )


def fetch_experiment(
    target_folder: Path, experiment_id: str, exclude_results: bool = False
) -> None:
    """Fetch an experiment into an existing context folder under
    ``experiments/<experiment_id>/``.
    """
    db_root = get_db_path()
    exp_dir = db_root / "experiment" / experiment_id
    if not exp_dir.is_dir():
        raise ValueError(
            f"Experiment {experiment_id!r} not found in database (expected {exp_dir})"
        )
    if not target_folder.is_dir():
        raise ValueError(f"Target folder does not exist: {target_folder}")

    with DatabaseLock(db_root):
        dst_root = target_folder / "experiments"
        dst_root.mkdir(exist_ok=True)
        dst = dst_root / experiment_id
        if dst.exists():
            raise ValueError(f"Experiment {experiment_id!r} already present at {dst}")
        ignore_pattern = IGNORE_METADATA_PATTERN
        if exclude_results:
            # Ignore everything that's NOT either "script.py" or "description.md"
            ignore_pattern = lambda _, names: [  # noqa: E731
                n for n in names if n not in ("script.py", "description.md")
            ]
        shutil.copytree(exp_dir, dst, ignore=ignore_pattern)
        _make_writable(dst)


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

    with DatabaseLock(db_root):
        exp_root = db_root / "experiment"
        if not exp_root.is_dir():
            return []

        for meta_path in sorted(exp_root.glob("*/metadata.json")):
            try:
                data = json.loads(meta_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue

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
    lit_dir = db_root / "literature" / literature_id
    if not lit_dir.is_dir():
        raise ValueError(
            f"Literature review {literature_id!r} not found in database "
            f"(expected {lit_dir})"
        )
    if not target_folder.is_dir():
        raise ValueError(f"Target folder does not exist: {target_folder}")

    with DatabaseLock(db_root):
        dst_root = target_folder / "literature"
        dst_root.mkdir(exist_ok=True)
        dst = dst_root / literature_id
        if dst.exists():
            raise ValueError(f"Literature {literature_id!r} already present at {dst}")
        shutil.copytree(lit_dir, dst, ignore=IGNORE_METADATA_PATTERN)
        _make_writable(dst)


def list_entries(entry_type: str, parent_theory: str | None = None) -> list[dict]:
    """List stored entries of the given type, sorted by creation time."""
    if entry_type not in VALID_CATEGORIES:
        raise ValueError(
            f"Unknown entry type {entry_type!r}. Must be one of: "
            f"{', '.join(VALID_CATEGORIES)}"
        )

    db_root = get_db_path()

    results: list[dict] = []

    with DatabaseLock(db_root):
        pattern = db_root / entry_type / "*" / "metadata.json"

        for meta_path in sorted(db_root.glob(str(pattern.relative_to(db_root)))):
            try:
                data = json.loads(meta_path.read_text())
                if (
                    entry_type in ("review", "experiment")
                    and parent_theory
                    and data.get("parent_theory") != parent_theory
                ):
                    continue
                results.append(data)
            except (json.JSONDecodeError, OSError):
                continue

    results.sort(key=lambda d: d.get("created_at", ""))
    return results


def sample_theories(
    num_theories: int, purpose: Literal["scoring", "mutation"]
) -> list[str]:
    db_root = get_db_path()
    with DatabaseLock(db_root):
        population_path = _population_path(db_root)
        population = _load_population(population_path)
        if not population:
            return []
        if purpose == "scoring":
            samples = population.sample_parents(
                k=min(
                    len(population.organisms),
                    num_theories,
                ),
                exclude_untrainable=False,
                replace=False,
                novelty_weight=0.0,
            )
        elif purpose == "mutation":
            samples = population.sample_parents(
                k=num_theories,
                exclude_untrainable=False,
            )
        else:
            raise ValueError(f"Unknown sampling purpose {purpose!r}")

        return [o.theory_id for o, _ in samples]


def rescore_theories(theory_scores: dict[str, float]) -> None:
    db_root = get_db_path()
    with DatabaseLock(db_root):
        population_path = _population_path(db_root)
        population = _load_population(population_path)
        if not population:
            raise RuntimeError("Population is empty; cannot rescore theories")

        # Step 1: Update scores for the procvided theories
        updated_theories = set()
        for organism, score in population.organisms:
            if organism.theory_id in theory_scores:
                score.score = theory_scores[organism.theory_id]
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

        _save_population(population, population_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    db_root = get_db_path(ensure_exists=False)
    if db_root.exists():
        with DatabaseLock(db_root):
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
    sp_init = sub.add_parser("init", help="Initialize a new database")

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
            "predict-experiments",
            "rank-predictions",
            "score-theories",
            "score-soundness",
            "rank-predictive-power",
            "polish-theory",
            "streamline-theory",
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
            "Literature review ID. Repeatable for refine-hypothesis and "
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

    # -- rescore ----------------------------------------------------------------
    sp_rescore = sub.add_parser(
        "rescore_theories", help="Submit updated scores for theories"
    )
    sp_rescore.add_argument(
        "theory_score_dict",
        help='Dictionary of theory IDs and their updated scores as a JSON object string (e.g. \'{"theory_id_1": 0.8, "theory_id_2": 0.3}\')',
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
            print(new_id)

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

        elif args.command == "list":
            entries = list_entries(
                args.entry_type, parent_theory=getattr(args, "parent_theory", None)
            )
            if args.json_output:
                print(json.dumps(entries, indent=2))
            else:
                if not entries:
                    print(f"No {args.entry_type} entries found.")
                else:
                    # Print table header
                    print(f"{'ID':<40} {'Created At':<28} {'Agent Type':<20}")
                    print("-" * 88)
                    for e in entries:
                        print(
                            f"{e.get('id', '?'):<40} "
                            f"{e.get('created_at', '?'):<28} "
                            f"{e.get('agent_type', '?'):<20}"
                        )

        elif args.command == "sample_theories":
            sampled_ids = sample_theories(
                num_theories=args.num_theories, purpose=args.purpose
            )
            print(", ".join(sampled_ids))

        elif args.command == "rescore_theories":
            theory_score_dict = json.loads(args.theory_score_dict)
            if not isinstance(theory_score_dict, dict):
                raise ValueError(
                    "theory_score_dict must be a JSON object mapping theory IDs to scores"
                )
            rescore_theories(theory_score_dict)

    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
