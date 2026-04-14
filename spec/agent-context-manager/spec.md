# Agent Context Manager

## Overview

The Agent Context Manager is a filesystem-based persistence and context-provisioning system for the Skills pipeline (`explore` → `write-theory` → `falsify-hypothesis` → `refine-hypothesis`). It solves two problems: (1) durably storing the output of each skill agent so results are never lost and can always be traced back, and (2) assembling the correct input context for the next agent in the pipeline by copying the right set of files into a working folder.

The system is deliberately separate from the framework agent system in `src/framework/` (which has its own `organisms/` persistence via `organism.py`). It is designed for the Claude Code skills defined in `src/claude_skills/skills/` — `explore`, `write-theory`, `falsify-hypothesis`, and `refine-hypothesis` — which currently write their output into ephemeral `tmp/` directories and have no durable storage or standardized handoff mechanism.

The UX is a Python CLI script (`context_manager.py`) with three subcommands:

- **`store_results`**: After a skill agent finishes and has written its output files into a folder, the pipeline runner calls `context_manager.py store_results --from_agent_type explorer --from_folder tmp/explore-abc123`. The command validates the folder contents, copies them into the immutable database under a generated ID, writes a `metadata.json`, and prints the new ID to stdout. If validation fails (e.g., no `.md` file present), it prints an error to stderr and exits with a non-zero code.

- **`create_context`**: Before launching the next agent, the pipeline runner calls `context_manager.py create_context --for_agent_type write-theory --target_folder tmp/write-theory-work --from_exploration E1`. This creates the target folder and populates it with a snapshot of the referenced exploration's files, laid out in a semi-structured way (e.g., `target_folder/exploration/report.md`, `target_folder/exploration/artifacts/...`). The downstream agent can freely modify its working copy without affecting the database.

- **`list`**: `context_manager.py list --type exploration` prints a table of stored IDs and their creation timestamps, sorted chronologically.

The database is a plain directory tree on disk. Once a result is stored under a given ID, it is immutable — files cannot be overwritten or deleted. This guarantees that any previous agent's exact environment can be reconstructed at any time, enabling isolated iteration on individual pipeline stages.

## Summary

The system consists of three layers: a storage layer, a context assembly layer, and a CLI layer.

**Storage layer.** The database lives at a configurable root path (defaulting to `.ai-scientist-db/` under the current working directory, overridable via the `AI_SCIENTIST_DB_PATH` environment variable). Under this root, results are organized by category: `exploration/`, `theory/`, and `theory/<theory_id>/review/`. Each stored result gets a unique ID (a timestamp + short UUID, e.g., `E_20260414_143052_a1b2c3` for explorations, `T_20260414_143100_d4e5f6` for theories, `R_20260414_143200_g7h8i9` for reviews). Within each ID's directory, the original agent output files are copied verbatim, plus a `metadata.json` is generated containing the creation timestamp, agent type, parent references, and any user-supplied key-value pairs. Immutability is enforced at the application level: `store_results` refuses to write into an existing ID directory and makes the directory read-only after writing.

**Context assembly layer.** The `create_context` command reads from the database and writes a structured snapshot into a target folder. The layout groups files by source type rather than replicating the database nesting. For example, when preparing context for `refine-hypothesis`, the target folder would contain `theory/` (the write-theory agent's full output) and `reviews/R1/`, `reviews/R2/` (each being the complete output of a falsify-hypothesis agent run). Each `create_context` invocation for a given agent type knows which upstream artifacts to require (via `--from_exploration`, `--from_theory`, `--from_review` flags) and copies them in full.

**Concurrency.** A single database-level lock file (`db_root/.lock`) is acquired before any write operation (`store_results`) and before any read operation (`create_context`, `list`) to ensure consistency. The lock uses `fcntl.flock` on Unix for advisory locking, with a configurable timeout. This is a coarse-grained lock intentionally — the operations are fast filesystem copies, so contention is unlikely and the simplicity is worth it.

**Data flow for the full pipeline:**

1. The `explore` skill runs and writes output into `tmp/explore-XXXX/`. The pipeline runner calls `store_results --from_agent_type explorer --from_folder tmp/explore-XXXX/`, receiving back an exploration ID (e.g., `E1`).
2. To run `write-theory`, the runner calls `create_context --for_agent_type write-theory --target_folder tmp/write-theory-work --from_exploration E1`. This copies the exploration report and artifacts into the target folder. The `write-theory` skill runs in that folder.
3. The runner calls `store_results --from_agent_type write-theory --from_folder tmp/write-theory-work`, receiving back a theory ID (e.g., `T1`).
4. To run `falsify-hypothesis`, the runner calls `create_context --for_agent_type falsify-hypothesis --target_folder tmp/falsify-work --from_theory T1`. The skill runs, producing a review.
5. The runner calls `store_results --from_agent_type falsify-hypothesis --from_folder tmp/falsify-work --parent_theory T1`, receiving back a review ID (e.g., `R1`). The review is stored nested under `theory/T1/review/R1/`.
6. To run `refine-hypothesis`, the runner calls `create_context --for_agent_type refine-hypothesis --target_folder tmp/refine-work --from_theory T1 --from_review R1`. This copies both the theory and the specific review into the target folder.
7. The runner stores the refined theory output as a new theory entry (`T2`), completely independent of `T1`.

## Implementation Plan

All new code will live in a single new file at `src/context_manager.py`. No existing files need to be modified for the core functionality. The implementation uses Python standard library modules (`argparse`, `json`, `shutil`, `os`, `fcntl`, `uuid`, `datetime`, `pathlib`, `sys`) plus `pydantic` for data models (already a project dependency in `pyproject.toml`) — no new dependencies are required.

### Constants and Configuration

A module-level section will define:

- `AGENT_TYPE_MAP`: A dictionary mapping CLI agent type names to their database category and expected primary markdown filename. Specifically: `"explorer"` → `("exploration", "report.md")`, `"write-theory"` → `("theory", "theory.md")`, `"refine-hypothesis"` → `("theory", "theory.md")`, `"falsify-hypothesis"` → `("review", "review.md")`.
- `ID_PREFIXES`: A dictionary mapping database categories to ID prefixes: `"exploration"` → `"E"`, `"theory"` → `"T"`, `"review"` → `"R"`.
- `DEFAULT_DB_DIR`: The string `".ai-scientist-db"`, used as the default database directory name.
- `ENV_DB_PATH`: The string `"AI_SCIENTIST_DB_PATH"`, the environment variable for overriding the database path.
- `LOCK_FILENAME`: The string `".lock"`.

### `generate_id(category: str) -> str`

A function that generates a unique ID for a stored result. It combines the category prefix (from `ID_PREFIXES`), a UTC timestamp formatted as `YYYYMMDD_HHMMSS`, and a 6-character hex UUID suffix. For example: `E_20260414_143052_a1b2c3`.

### `get_db_path() -> Path`

A function that returns the resolved database root path. It checks the `AI_SCIENTIST_DB_PATH` environment variable first; if not set, it returns `Path.cwd() / DEFAULT_DB_DIR`.

### `DatabaseLock`

A context manager class that acquires an exclusive advisory lock on `db_root/.lock` using `fcntl.flock(LOCK_EX)`. The `__enter__` method opens (or creates) the lock file and acquires the lock; `__exit__` releases it and closes the file handle. A `timeout` parameter (default 30 seconds) will be supported by attempting the lock in non-blocking mode with a retry loop.

### `store_results(from_agent_type: str, from_folder: Path, parent_theory: str | None, metadata_extra: dict[str, str]) -> str`

The core storage function. Steps:

1. Resolve `from_agent_type` via `AGENT_TYPE_MAP` to get `(category, expected_md)`.
2. Validate that `from_folder` exists and contains at least the primary markdown `.md` file and does not contain any file named medadata.json. Otherwise, raise a `ValueError` with a descriptive message.
3. If `from_agent_type` is `"falsify-hypothesis"`, require that `parent_theory` is provided and that the referenced theory exists in the database. Raise `ValueError` otherwise.
4. Acquire `DatabaseLock`.
5. Generate a new ID via `generate_id(category)`.
6. Determine the target directory:
   - For `"exploration"`: `db_root/exploration/<id>/`
   - For `"theory"` (from `write-theory` or `refine-hypothesis`): `db_root/theory/<id>/`
   - For `"review"` (from `falsify-hypothesis`): `db_root/theory/<parent_theory>/review/<id>/`
7. Verify the target directory does not already exist (defensive check against ID collision).
8. Copy the entire contents of `from_folder` into the target directory using `shutil.copytree`.
9. Write `metadata.json` into the target directory containing: `id`, `agent_type`, `category`, `created_at` (ISO 8601 UTC), `parent_theory` (if applicable), and any extra key-value pairs from `metadata_extra`.
10. Make the target directory and all its contents read-only (remove write permissions) to enforce immutability at the OS level.
11. Return the generated ID.

### `create_context(for_agent_type: str, target_folder: Path, from_exploration: str | None, from_theory: str | None, from_reviews: list[str] | None) -> None`

The context assembly function. Steps:

1. Validate the `for_agent_type` and determine which upstream references are required:
   - `"write-theory"` requires `--from_exploration`. Copies the exploration agent's output into `target_folder/exploration/`.
   - `"falsify-hypothesis"` requires `--from_theory`. Copies the theory agent's output into `target_folder/theory/`.
   - `"refine-hypothesis"` requires `--from_theory` and at least one `--from_review`. Copies the theory agent's output into `target_folder/theory/`, and the output of each specified falsify-hypothesis run into `target_folder/reviews/<review_id>/`.
2. Acquire `DatabaseLock` (shared-read would be ideal, but for simplicity we use the same exclusive lock — reads are fast).
3. Resolve the database paths for each referenced ID. Verify they exist; raise `ValueError` if any are missing.
4. For reviews, validate that each review ID actually belongs to the specified theory (i.e., lives under `db_root/theory/<theory_id>/review/<review_id>/`).
5. Create the `target_folder` (and parents).
6. Copy each upstream agent's stored output into the structured layout using `shutil.copytree`. When copying a theory's stored directory from the database, use an `ignore` function to exclude the `review/` subdirectory — that subdirectory is a database-level nesting for falsify-hypothesis outputs, not part of the theory agent's original output.

### `list_entries(entry_type: str) -> list[dict]`

A function that lists all stored entries of a given type. Steps:

1. Map `entry_type` to a database category (`"exploration"`, `"theory"`, or `"review"`).
2. Acquire `DatabaseLock`.
3. For `"exploration"` and `"theory"`: glob `db_root/<category>/*/metadata.json`, load each, collect ID and `created_at`.
4. For `"review"`: glob `db_root/theory/*/review/*/metadata.json`.
5. Sort by `created_at` ascending.
6. Return the list of dicts.

### CLI Entry Point (`main()`)

An `argparse`-based CLI with three subcommands:

**`store_results`** subcommand:
- `--from_agent_type` (required): One of `explorer`, `write-theory`, `falsify-hypothesis`, `refine-hypothesis`.
- `--from_folder` (required): Path to the folder containing agent output.
- `--parent_theory` (optional): Required when `--from_agent_type` is `falsify-hypothesis`.
- `--metadata` (optional, repeatable): Extra key-value pairs in `key=value` format.
- On success, prints the new ID to stdout. On error, prints to stderr and exits with code 1.

**`create_context`** subcommand:
- `--for_agent_type` (required): One of `write-theory`, `falsify-hypothesis`, `refine-hypothesis`.
- `--target_folder` (required): Path to the folder to populate.
- `--from_exploration` (optional): Exploration ID.
- `--from_theory` (optional): Theory ID.
- `--from_review` (optional, repeatable via `append` action): Review ID(s).
- On success, exits with code 0. On error, prints to stderr and exits with code 1.

**`list`** subcommand:
- `--type` (required): One of `exploration`, `theory`, `review`.
- Prints a table of IDs and timestamps to stdout, one per line, sorted by timestamp.

### Data Types

**`StoredMetadata`** (`pydantic.BaseModel`): Fields are `id: str`, `agent_type: str`, `category: str`, `created_at: str`, `parent_theory: str | None = None`, `extra: dict[str, str] = {}`. Uses Pydantic's built-in `.model_dump()` for serialization to dict and `.model_validate()` for deserialization from dict/JSON, following the same Pydantic conventions used in `src/framework/config.py` (`FrameworkConfig`, `AgentConfig`).

### Error Handling

All functions that interact with the database raise `ValueError` for user-facing errors (missing files, invalid references, missing required flags). The CLI `main()` catches these, prints them to stderr, and exits with code 1. Unexpected errors (filesystem permission issues, lock timeouts) propagate as their native exception types and also result in a non-zero exit.

## Implementation Phases

### Phase 1: Core Storage

This phase delivers the database structure, ID generation, locking, and the `store_results` command for the `explorer` agent type only.

Implement `get_db_path()`, `generate_id()`, `DatabaseLock`, the `StoredMetadata` Pydantic model, and `store_results()` — but initially only handling the `explorer` → `exploration/` mapping. Implement the `main()` CLI entry point with just the `store_results` subcommand. Validation at this stage checks only that the source folder exists and contains at least one `.md` file. Write a manual test: create a folder with a `report.md` and an `artifacts/` subdirectory, run `store_results`, verify the database directory structure is correct, `metadata.json` is written, and the directory is read-only.

### Phase 2: Full `store_results` for All Agent Types

Extend `store_results` to handle all four agent types: `explorer`, `write-theory`, `falsify-hypothesis`, and `refine-hypothesis`. This includes the `--parent_theory` validation for `falsify-hypothesis` (verifying the referenced theory exists in the database) and the nested `theory/<id>/review/<review_id>/` storage layout for reviews. Add the `--metadata` flag for arbitrary key-value pairs.

### Phase 3: `create_context` Command

Implement `create_context()` and its CLI subcommand. Handle all three target agent types (`write-theory`, `falsify-hypothesis`, `refine-hypothesis`) with their respective required flags and copy logic. The key complexity here is the `refine-hypothesis` case, which must copy the theory agent's output (excluding the database-level `review/` subdirectory) and one or more falsify-hypothesis outputs into a flat `reviews/` layout. Test by running the full pipeline manually: store an exploration, create context for write-theory, store the theory, create context for falsify-hypothesis, store the falsify-hypothesis output as a review, create context for refine-hypothesis — verifying the final folder contains the correct files at each step.

### Phase 4: `list` Command and Polish

Implement `list_entries()` and the `list` CLI subcommand. Format output as a simple table with columns for ID, created timestamp, and agent type. Add the `--type` filter. Also add a `--json` output flag for machine-readable output. At this stage, also add any missing edge-case handling: graceful behavior when the database directory doesn't exist yet (for `list` and `create_context`), helpful error messages for common mistakes (e.g., passing a theory ID where an exploration ID is expected), and confirmation that file permissions are correctly set on macOS and Linux.

## Open Questions

1. **Review-to-theory validation in `create_context`**: When `--from_review R1` is passed alongside `--from_theory T1`, should the system strictly enforce that `R1` is stored under `T1`'s review directory, or should it allow cross-referencing reviews from other theories? Strict enforcement is safer and prevents accidental mismatches, but cross-referencing could be useful for comparing how different theories respond to the same critique.

2. **Immutability enforcement mechanism**: The spec calls for making directories read-only after writing. On macOS, `chmod -R a-w` is straightforward, but some tools (e.g., `shutil.rmtree`) may fail on read-only trees. Should we provide a companion `context_manager.py gc` or `context_manager.py delete` command that can remove entries when explicitly asked, or rely on users knowing to `chmod +w` before cleanup?

3. **Large artifact handling**: Exploration outputs can include multi-megabyte `results.json` files and image artifacts (as seen in `output/explore/` where `results.json` is 17MB). Should `store_results` impose a size limit or warn about large files? Should `create_context` support selective copying (e.g., skip `results.json` but include plots)?

4. **Theory refinement lineage**: When `refine-hypothesis` produces a new theory and it's stored via `store_results --from_agent_type refine-hypothesis`, should the metadata automatically record the ID of the original theory and the reviews that informed the refinement? This would require either an additional `--parent_theory` flag on `store_results` for the `refine-hypothesis` agent type, or a convention where the caller passes this as `--metadata original_theory=T1`.

5. **Database compaction and migration**: As the database grows with immutable entries, disk usage will increase monotonically. Is there a future need for archiving, compression, or migration tooling? This doesn't need to be in the initial implementation but would affect the choice of directory structure if planned for.

6. **Concurrency model**: The current design uses a single exclusive lock for all operations. If the pipeline is later parallelized (e.g., multiple `falsify-hypothesis` agents running concurrently against different theories), the lock could become a bottleneck. Should the locking be per-category or per-entry instead of database-wide? The single lock is simpler and sufficient for the current sequential pipeline, but the question is worth flagging.