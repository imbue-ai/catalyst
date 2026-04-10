"""Base agent classes with invocation logging, retry, and error feedback.

Design informed by imbue-ai/knowledge_seeker:
- Retry with exponential backoff on all LLM calls
- Error feedback injection: on parse failure, re-prompt with correction
- Structured JSON schema hints in prompts
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic

from ..logging import InvocationRecord, new_invocation_id, log_invocation

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from an agent invocation."""
    raw_output: str
    parsed: Any
    invocation_id: str
    duration_seconds: float


class AgentBase(ABC):
    """Abstract base class for all agents."""

    agent_type: str = "base"

    def __init__(
        self,
        log_dir: Path | None = None,
        timeout_seconds: float = 300,
        max_retries: int = 3,
    ):
        self.log_dir = log_dir
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def invoke(
        self,
        prompt: str,
        file_context: dict[str, str] | None = None,
        organism_id: str | None = None,
        experiment_id: str | None = None,
    ) -> AgentResult:
        """Run the agent with retry and logging.

        Retries with exponential backoff on failure (knowledge_seeker pattern).
        On parse failure, injects error feedback and retries (self-correction).
        """
        file_context = file_context or {}
        invocation_id = new_invocation_id()

        raw_output = ""
        last_error = None

        for attempt in range(self.max_retries):
            start = time.time()

            # Build prompt with error feedback if retrying
            effective_prompt = prompt
            if last_error and attempt > 0:
                effective_prompt = (
                    f"IMPORTANT: Your previous response had a parsing error: "
                    f"{last_error}\nPlease ensure your output follows the "
                    f"requested format exactly.\n\n{prompt}"
                )

            try:
                raw_output = self._execute(effective_prompt, file_context)
                duration = time.time() - start
            except Exception as e:
                duration = time.time() - start
                raw_output = f"ERROR: {type(e).__name__}: {e}"
                logger.warning(
                    f"Agent {self.agent_type} attempt {attempt+1}/{self.max_retries} "
                    f"failed: {e}"
                )
                if attempt < self.max_retries - 1:
                    backoff = 2 ** attempt
                    time.sleep(backoff)
                    continue
                break

            # Try parsing — if it fails, retry with feedback
            try:
                parsed = self._parse_response(raw_output)
                # Check if parsed result indicates a problem
                if isinstance(parsed, dict) and parsed.get("raw") and not any(
                    k in parsed for k in ("theory", "scores", "observations", "verified")
                ):
                    # Fallback parse — might want to retry
                    if attempt < self.max_retries - 1 and "ERROR" not in raw_output:
                        last_error = "Could not extract structured data from response"
                        backoff = 2 ** attempt
                        time.sleep(backoff)
                        continue
                break
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Agent {self.agent_type} parse error on attempt "
                    f"{attempt+1}: {last_error}"
                )
                if attempt < self.max_retries - 1:
                    backoff = 2 ** attempt
                    time.sleep(backoff)
                    continue
                parsed = self._parse_response(raw_output)
                break
        else:
            parsed = self._parse_response(raw_output)

        # Log the invocation
        if self.log_dir:
            record = InvocationRecord(
                id=invocation_id,
                agent_type=self.agent_type,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                prompt=prompt,
                file_inputs=file_context,
                output=raw_output,
                duration_seconds=duration,
                organism_id=organism_id,
                experiment_id=experiment_id,
            )
            log_invocation(record, self.log_dir)

        return AgentResult(
            raw_output=raw_output,
            parsed=parsed,
            invocation_id=invocation_id,
            duration_seconds=duration,
        )

    @abstractmethod
    def _execute(self, prompt: str, file_context: dict[str, str]) -> str:
        """Execute the agent's task. Subclasses implement this."""

    def _parse_response(self, raw_output: str) -> Any:
        """Parse the raw output. Override for structured parsing."""
        return raw_output


class LLMAgent(AgentBase):
    """Agent that makes direct Anthropic SDK API calls."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: str = "",
        log_dir: Path | None = None,
        timeout_seconds: float = 300,
        max_retries: int = 3,
    ):
        super().__init__(
            log_dir=log_dir,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt
        self._client = anthropic.Anthropic()

    def _execute(self, prompt: str, file_context: dict[str, str]) -> str:
        # Build the user message with file context
        parts = []
        if file_context:
            parts.append("## File Context\n")
            for filename, content in file_context.items():
                parts.append(f"### {filename}\n```\n{content}\n```\n")
            parts.append("## Task\n")
        parts.append(prompt)

        full_prompt = "\n".join(parts)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": full_prompt}],
        }
        if self.system_prompt:
            kwargs["system"] = self.system_prompt
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature

        response = self._client.messages.create(**kwargs)
        return response.content[0].text


class CLIAgent(AgentBase):
    """Agent that invokes the `claude` CLI as a subprocess.

    Gives the subagent access to file reading, shell execution, etc.
    """

    def __init__(
        self,
        model: str | None = None,
        log_dir: Path | None = None,
        timeout_seconds: float = 600,
        allowed_tools: list[str] | None = None,
        max_retries: int = 3,
    ):
        super().__init__(
            log_dir=log_dir,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self.model = model
        self.allowed_tools = allowed_tools or ["Read", "Bash", "Glob", "Grep"]

    def _execute(self, prompt: str, file_context: dict[str, str]) -> str:
        # Build context-enriched prompt
        parts = []
        if file_context:
            parts.append("## File Context\n")
            for filename, content in file_context.items():
                parts.append(f"### {filename}\n```\n{content}\n```\n")
            parts.append("## Task\n")
        parts.append(prompt)

        full_prompt = "\n".join(parts)

        cmd = ["claude", "--print", "--prompt", full_prompt]
        if self.model:
            cmd.extend(["--model", self.model])
        for tool in self.allowed_tools:
            cmd.extend(["--allowedTools", tool])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )

        if result.returncode != 0:
            return f"CLI ERROR (exit {result.returncode}):\n{result.stderr}\n{result.stdout}"
        return result.stdout
