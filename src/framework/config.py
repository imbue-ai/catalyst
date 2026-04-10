"""Framework configuration management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Configuration for a specific agent type."""
    model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_seconds: float = 300
    use_cli: bool = False


class FrameworkConfig(BaseModel):
    """Top-level configuration for the theory evolution framework."""
    phenomenon_description: str = "Bifurcation in shallow ReLU MLPs"
    phenomenon_description_path: Path | None = None
    organisms_dir: Path = Path("organisms")
    logs_dir: Path = Path("logs")
    max_population: int = 20
    generations: int = 5
    experiments_per_organism_per_generation: int = 2
    selection_strategy: str = "tournament"  # "tournament", "top_k", "roulette"
    tournament_size: int = 3
    mutation_rate: float = 0.8
    elite_count: int = 2
    cli_tool_path: str = "python -m shallow_mlps.cli"
    agent_configs: dict[str, AgentConfig] = Field(default_factory=lambda: {
        "experimenter": AgentConfig(use_cli=True, timeout_seconds=600),
        "interpreter": AgentConfig(temperature=0.3, max_tokens=4096),
        "scorer": AgentConfig(temperature=0.3, max_tokens=2048),
        "mutator": AgentConfig(temperature=0.9, max_tokens=8192),
        "verifier": AgentConfig(use_cli=True, timeout_seconds=600),
    })

    @classmethod
    def from_yaml(cls, path: Path) -> FrameworkConfig:
        """Load configuration from a YAML file."""
        data = yaml.safe_load(path.read_text())
        return cls(**data)

    @classmethod
    def from_json(cls, path: Path) -> FrameworkConfig:
        """Load configuration from a JSON file."""
        import json
        data = json.loads(path.read_text())
        return cls(**data)

    def save_yaml(self, path: Path) -> None:
        """Save configuration to a YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.model_dump(mode="json")
        # Convert Path objects to strings
        for key in ("organisms_dir", "logs_dir", "phenomenon_description_path"):
            if data.get(key) is not None:
                data[key] = str(data[key])
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def get_agent_config(self, agent_type: str) -> AgentConfig:
        """Get config for a specific agent type, with defaults."""
        return self.agent_configs.get(agent_type, AgentConfig())

    def get_phenomenon_description(self) -> str:
        """Get the full phenomenon description text."""
        if self.phenomenon_description_path and self.phenomenon_description_path.exists():
            return self.phenomenon_description_path.read_text()
        return self.phenomenon_description
