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
    "write-theory": ("theory", "theory.md"),
    "refine-hypothesis": ("theory", "theory.md"),
    "falsify-hypothesis": ("review", "review.md"),
    "suggest-expansions": ("review", "review.md"),
    "expand-theory": ("theory", "theory.md"),
}

ID_PREFIXES: dict[str, str] = {
    "exploration": "E",
    "literature": "L",
    "theory": "T",
    "review": "R",
}

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

    # --- review-producing agents require a parent theory ---
    review_agents = ("falsify-hypothesis", "suggest-expansions")
    if from_agent_type in review_agents:
        if not parent_theory:
            raise ValueError(
                f"--parent_theory is required when storing {from_agent_type} results"
            )
        theory_dir = db_root / "theory" / parent_theory
        if not theory_dir.is_dir():
            raise ValueError(
                f"Referenced parent theory {parent_theory!r} does not exist "
                f"in the database (expected {theory_dir})"
            )

    with DatabaseLock(db_root):
        new_id = generate_id(category)

        # --- determine target directory ---
        if category in ("exploration", "literature", "theory", "review"):
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
            parent_theory=parent_theory if from_agent_type in review_agents else None,
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
    from_literature: str | None = None,
    from_theory: str | None = None,
    from_reviews: list[str] | None = None,
) -> None:
    """Assemble upstream artifacts into *target_folder* for the next agent."""
    db_root = get_db_path()

    # --- validate required references per agent type ---
    if for_agent_type == "write-theory":
        if not from_exploration:
            raise ValueError("--from_exploration is required for write-theory")
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

        if from_literature:
            literature_dir = db_root / "literature" / from_literature
            if not literature_dir.is_dir():
                raise ValueError(
                    f"Literature review {from_literature!r} not found in database "
                    f"(expected {literature_dir})"
                )

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
            if from_literature:
                ldst = target_folder / "literature"
                shutil.copytree(literature_dir, ldst)  # type: ignore[possibly-undefined]
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

        elif for_agent_type == "review-theory":
            dst = target_folder / "theory.md"
            src_theory_md = theory_dir / "theory.md"  # type: ignore[possibly-undefined]
            if src_theory_md.exists():
                shutil.copy2(src_theory_md, dst)
                _make_writable(dst)


def list_entries(entry_type: str, parent_theory: str | None = None) -> list[dict]:
    """List stored entries of the given type, sorted by creation time."""
    valid = ("exploration", "literature", "theory", "review")
    if entry_type not in valid:
        raise ValueError(
            f"Unknown entry type {entry_type!r}. Must be one of: {', '.join(valid)}"
        )

    db_root = get_db_path()

    results: list[dict] = []

    with DatabaseLock(db_root):
        if entry_type in ("exploration", "literature", "theory", "review"):
            pattern = db_root / entry_type / "*" / "metadata.json"
        else:
            raise ValueError(f"Unknown entry type: {entry_type}")

        for meta_path in sorted(db_root.glob(str(pattern.relative_to(db_root)))):
            try:
                data = json.loads(meta_path.read_text())
                if (
                    entry_type == "review"
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
    sp_ctx.add_argument("--from_literature", default=None, help="Literature review ID")
    sp_ctx.add_argument("--from_theory", default=None, help="Theory ID")
    sp_ctx.add_argument(
        "--from_review",
        action="append",
        default=[],
        dest="from_reviews",
        help="Review ID (repeatable)",
    )

    # -- list ----------------------------------------------------------------
    sp_list = sub.add_parser("list", help="List stored entries")
    sp_list.add_argument(
        "--type",
        required=True,
        choices=["exploration", "literature", "theory", "review"],
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
                from_literature=args.from_literature,
                from_theory=args.from_theory,
                from_reviews=args.from_reviews or None,
            )

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
