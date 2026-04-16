"""Agent Context Manager — filesystem-based persistence and context assembly for the Skills pipeline.

Provides four CLI subcommands:
  store_results  — persist agent output into an immutable database
  create_context — assemble upstream artifacts into a working folder for the next agent
  list           — enumerate stored entries by type
  init           — initialize a new database
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
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants & configuration
# ---------------------------------------------------------------------------

AGENT_TYPE_MAP: dict[str, tuple[str, str]] = {
    # agent_type -> (database_category, expected_primary_md)
    "explorer": ("exploration", "report.md"),
    "literature-review": ("literature", "summary.md"),
    "search-literature": ("literature", "summary.md"),
    "write-theory": ("theory", "theory.md"),
    "refine-hypothesis": ("theory", "theory.md"),
    "falsify-hypothesis": ("review", "review.md"),
    "suggest-expansions": ("review", "review.md"),
    "expand-theory": ("theory", "theory.md"),
    "run-experiment": ("experiment", "description.md"),
}

ID_PREFIXES: dict[str, str] = {
    "exploration": "E",
    "literature": "L",
    "theory": "T",
    "review": "R",
    "experiment": "X",
}

VALID_CATEGORIES: tuple[str, ...] = (
    "exploration",
    "literature",
    "theory",
    "review",
    "experiment",
)

DEFAULT_DB_DIR = ".ai-scientist-db"
ENV_DB_PATH = "AI_SCIENTIST_DB_PATH"
LOCK_FILENAME = ".lock"

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


class DatabaseLock:
    """Context manager that acquires an exclusive advisory lock on the DB."""

    def __init__(self, db_root: Path, timeout: float = 30.0) -> None:
        self.lock_path = db_root / LOCK_FILENAME
        self.timeout = timeout
        self._fd: int | None = None

    def __enter__(self) -> "DatabaseLock":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
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
        if self._fd is not None:
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


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------


def _make_readonly(path: Path) -> None:
    """Recursively remove write permissions from *path*."""
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

    category, expected_md = AGENT_TYPE_MAP[from_agent_type]

    # --- validate source folder ---
    if not from_folder.is_dir():
        raise ValueError(f"Source folder does not exist: {from_folder}")
    if not (from_folder / expected_md).is_file():
        raise ValueError(
            f"Source folder is missing the required file {expected_md!r}: {from_folder}"
        )
    if (from_folder / "metadata.json").exists():
        raise ValueError(
            "Source folder must not contain a file named metadata.json "
            "(it will be generated automatically)"
        )

    db_root = get_db_path()

    # --- agents allowed to attach a parent_theory ---
    review_agents = ("falsify-hypothesis", "suggest-expansions")
    parent_theory_agents = review_agents + ("run-experiment",)

    if from_agent_type in review_agents and not parent_theory:
        raise ValueError(
            f"--parent_theory is required when storing {from_agent_type} results"
        )
    if parent_theory and from_agent_type in parent_theory_agents:
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
        shutil.copytree(from_folder, target_dir)

        # --- write metadata ---
        meta = StoredMetadata(
            id=new_id,
            agent_type=from_agent_type,
            category=category,
            created_at=datetime.now(timezone.utc).isoformat(),
            parent_theory=parent_theory if from_agent_type in parent_theory_agents else None,
            extra=metadata_extra or {},
        )
        (target_dir / "metadata.json").write_text(
            json.dumps(meta.model_dump(), indent=2) + "\n"
        )

        # --- make immutable ---
        _make_readonly(target_dir)

    return new_id


def create_context(
    for_agent_type: str,
    target_folder: Path,
    from_exploration: str | None = None,
    from_literatures: list[str] | None = None,
    from_theory: str | None = None,
    from_reviews: list[str] | None = None,
) -> None:
    """Assemble upstream artifacts into *target_folder* for the next agent."""
    db_root = get_db_path()

    # --- validate required references per agent type ---
    if for_agent_type == "write-theory":
        if not from_exploration:
            raise ValueError("--from_exploration is required for write-theory")
        if from_literatures and len(from_literatures) > 1:
            raise ValueError(
                "write-theory accepts at most one --from_literature "
                "(refine-hypothesis and expand-theory support multiple)"
            )
    elif for_agent_type in ("falsify-hypothesis", "suggest-expansions"):
        if not from_theory:
            raise ValueError(f"--from_theory is required for {for_agent_type}")
    elif for_agent_type in ("refine-hypothesis", "expand-theory"):
        if not from_theory:
            raise ValueError(f"--from_theory is required for {for_agent_type}")
        if not from_reviews:
            raise ValueError(
                f"At least one --from_review is required for {for_agent_type}"
            )
    elif for_agent_type == "review-theory":
        if not from_theory:
            raise ValueError("--from_theory is required for review-theory")
    else:
        raise ValueError(
            f"Unknown target agent type {for_agent_type!r}. "
            f"Must be one of: write-theory, falsify-hypothesis, refine-hypothesis, "
            f"review-theory, suggest-expansions, expand-theory"
        )

    with DatabaseLock(db_root):
        # --- resolve and validate paths ---
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

        if from_theory:
            theory_dir = db_root / "theory" / from_theory
            if not theory_dir.is_dir():
                raise ValueError(
                    f"Theory {from_theory!r} not found in database "
                    f"(expected {theory_dir})"
                )

        if from_reviews:
            for rid in from_reviews:
                review_dir = db_root / "review" / rid
                if not review_dir.is_dir():
                    raise ValueError(
                        f"Review {rid!r} not found in database (expected {review_dir})"
                    )

        # --- create target and copy ---
        target_folder.mkdir(parents=True, exist_ok=True)

        if for_agent_type == "write-theory":
            dst = target_folder / "exploration"
            shutil.copytree(
                exploration_dir,  # type: ignore[possibly-undefined]
                dst,
            )
            _make_writable(dst)
            if literature_dirs:
                # write-theory uses flat layout (single literature review).
                _, lit_dir = literature_dirs[0]
                ldst = target_folder / "literature"
                shutil.copytree(lit_dir, ldst)
                _make_writable(ldst)

        elif for_agent_type in ("falsify-hypothesis", "suggest-expansions"):
            dst = target_folder / "theory"
            shutil.copytree(
                theory_dir,  # type: ignore[possibly-undefined]
                dst,
            )
            _make_writable(dst)

        elif for_agent_type in ("refine-hypothesis", "expand-theory"):
            dst = target_folder / "theory"
            shutil.copytree(
                theory_dir,  # type: ignore[possibly-undefined]
                dst,
            )
            _make_writable(dst)
            reviews_root = target_folder / "reviews"
            reviews_root.mkdir(exist_ok=True)
            for rid in from_reviews:  # type: ignore[union-attr]
                src = db_root / "review" / rid
                rdst = reviews_root / rid
                shutil.copytree(src, rdst)
                _make_writable(rdst)
            if literature_dirs:
                # refine-hypothesis / expand-theory use nested layout so
                # multiple literature reviews (including ones added mid-run
                # via `add_literature`) can coexist.
                lit_root = target_folder / "literature"
                lit_root.mkdir(exist_ok=True)
                for lid, lit_dir in literature_dirs:
                    ldst = lit_root / lid
                    shutil.copytree(lit_dir, ldst)
                    _make_writable(ldst)

        elif for_agent_type == "review-theory":
            dst = target_folder / "theory.md"
            src_theory_md = theory_dir / "theory.md"  # type: ignore[possibly-undefined]
            if src_theory_md.exists():
                shutil.copy2(src_theory_md, dst)
                _make_writable(dst)


def add_experiment(target_folder: Path, experiment_id: str) -> None:
    """Add an experiment to an existing context folder under
    ``experiments/<experiment_id>/``.

    Intended for mid-run integration: a writing skill invokes
    ``run-experiment``, receives a new ``X_...`` ID, and merges its
    contents into its own context via this command without having to
    rebuild the whole context folder.
    """
    db_root = get_db_path()
    exp_dir = db_root / "experiment" / experiment_id
    if not exp_dir.is_dir():
        raise ValueError(
            f"Experiment {experiment_id!r} not found in database "
            f"(expected {exp_dir})"
        )
    if not target_folder.is_dir():
        raise ValueError(f"Target folder does not exist: {target_folder}")

    with DatabaseLock(db_root):
        dst_root = target_folder / "experiments"
        dst_root.mkdir(exist_ok=True)
        dst = dst_root / experiment_id
        if dst.exists():
            raise ValueError(
                f"Experiment {experiment_id!r} already present at {dst}"
            )
        shutil.copytree(exp_dir, dst)
        _make_writable(dst)


def search_experiments(
    query: str | None = None,
    tags: list[str] | None = None,
    parent_theory: str | None = None,
    parent_review: str | None = None,
    parent_skill: str | None = None,
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
    query_tokens = [
        t.lower() for t in (query or "").split() if len(t) >= 3
    ]

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
            if parent_skill and extra.get("parent_skill") != parent_skill:
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
                score += sum(
                    1 for tok in query_tokens if tok in " ".join(entry_tags)
                )
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


def add_literature(target_folder: Path, literature_id: str) -> None:
    """Add a literature review to an existing context folder under
    ``literature/<literature_id>/``.

    Intended for mid-run integration: a writing skill invokes
    ``search-literature``, receives a new ``L_...`` ID, and merges its
    contents into its own context via this command without having to
    rebuild the whole context folder.
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
            raise ValueError(
                f"Literature {literature_id!r} already present at {dst}"
            )
        shutil.copytree(lit_dir, dst)
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
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
    sp_ctx.add_argument("--from_theory", default=None, help="Theory ID")
    sp_ctx.add_argument(
        "--from_review",
        action="append",
        default=[],
        dest="from_reviews",
        help="Review ID (repeatable)",
    )

    # -- add_literature ------------------------------------------------------
    sp_add_lit = sub.add_parser(
        "add_literature",
        help=(
            "Add a literature review to an existing context folder. "
            "Use this to fold a mid-run search-literature result into a "
            "writing skill's existing context."
        ),
    )
    sp_add_lit.add_argument(
        "--target_folder",
        required=True,
        type=Path,
        help="Existing context folder produced by a prior create_context call",
    )
    sp_add_lit.add_argument(
        "--from_literature",
        required=True,
        help="Literature review ID to add (nested under literature/<L_ID>/)",
    )

    # -- add_experiment ------------------------------------------------------
    sp_add_exp = sub.add_parser(
        "add_experiment",
        help=(
            "Add an experiment to an existing context folder. "
            "Use this to fold a mid-run run-experiment result (or a prior "
            "experiment surfaced via search_experiments) into a writing "
            "skill's existing context."
        ),
    )
    sp_add_exp.add_argument(
        "--target_folder",
        required=True,
        type=Path,
        help="Existing context folder produced by a prior create_context call",
    )
    sp_add_exp.add_argument(
        "--from_experiment",
        required=True,
        help="Experiment ID to add (nested under experiments/<X_ID>/)",
    )

    # -- search_experiments --------------------------------------------------
    sp_search = sub.add_parser(
        "search_experiments",
        help=(
            "Search stored experiments by substring match on description "
            "and tags. Returns matching experiment IDs with short previews."
        ),
    )
    sp_search.add_argument(
        "--query",
        default=None,
        help="Free-text query (tokens >=3 chars are matched against description + tags)",
    )
    sp_search.add_argument(
        "--tag",
        action="append",
        default=[],
        dest="tags",
        help="Require a specific tag on the experiment (repeatable)",
    )
    sp_search.add_argument(
        "--parent_theory",
        default=None,
        help="Filter to experiments run in support of a specific theory",
    )
    sp_search.add_argument(
        "--parent_review",
        default=None,
        help="Filter to experiments run in support of a specific review",
    )
    sp_search.add_argument(
        "--parent_skill",
        default=None,
        help="Filter to experiments invoked by a specific skill name",
    )
    sp_search.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of results to return",
    )
    sp_search.add_argument(
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

    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            db_path = get_db_path(ensure_exists=False)
            if db_path.exists():
                raise RuntimeError(f"Database path already exists: {db_path}")
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
                from_theory=args.from_theory,
                from_reviews=args.from_reviews or None,
            )

        elif args.command == "add_literature":
            add_literature(
                target_folder=args.target_folder.resolve(),
                literature_id=args.from_literature,
            )

        elif args.command == "add_experiment":
            add_experiment(
                target_folder=args.target_folder.resolve(),
                experiment_id=args.from_experiment,
            )

        elif args.command == "search_experiments":
            hits = search_experiments(
                query=args.query,
                tags=args.tags or None,
                parent_theory=args.parent_theory,
                parent_review=args.parent_review,
                parent_skill=args.parent_skill,
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

    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
