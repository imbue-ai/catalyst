"""Invocation record logging and replay for agent calls."""

from __future__ import annotations

import dataclasses
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclasses.dataclass
class InvocationRecord:
    """A complete record of a single agent invocation."""
    id: str
    agent_type: str
    timestamp: str
    prompt: str
    file_inputs: dict[str, str]
    output: str
    duration_seconds: float
    organism_id: str | None = None
    experiment_id: str | None = None
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InvocationRecord:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def new_invocation_id() -> str:
    """Generate a unique invocation ID."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:8]
    return f"inv_{ts}_{short}"


def log_invocation(record: InvocationRecord, log_dir: Path) -> Path:
    """Write an invocation record to disk.

    Returns the path to the saved record.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{record.id}.json"

    # For large file inputs, store a reference instead of inline
    file_inputs_for_save = {}
    for filename, content in record.file_inputs.items():
        if len(content) > 100_000:
            # Store large files as references
            file_inputs_for_save[filename] = f"<large_file: {len(content)} bytes>"
        else:
            file_inputs_for_save[filename] = content

    save_data = record.to_dict()
    save_data["file_inputs"] = file_inputs_for_save
    path.write_text(json.dumps(save_data, indent=2))
    return path


def load_invocation(record_path: Path) -> InvocationRecord:
    """Load an invocation record from disk."""
    data = json.loads(record_path.read_text())
    return InvocationRecord.from_dict(data)


def list_invocations(
    log_dir: Path,
    agent_type: str | None = None,
    organism_id: str | None = None,
    limit: int | None = None,
) -> list[InvocationRecord]:
    """Query logged invocations with optional filters."""
    if not log_dir.exists():
        return []

    records = []
    for path in sorted(log_dir.glob("inv_*.json"), reverse=True):
        try:
            record = load_invocation(path)
        except (json.JSONDecodeError, KeyError):
            continue

        if agent_type and record.agent_type != agent_type:
            continue
        if organism_id and record.organism_id != organism_id:
            continue

        records.append(record)
        if limit and len(records) >= limit:
            break

    return records
