"""Platform-neutral AI backend contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class AIBackendError(RuntimeError):
    """A generation backend could not complete a request."""


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    prompt: str
    system_prompt: str = ""
    temperature: float | None = None
    response_schema: dict[str, Any] | None = None
    schema_name: str = "generated_response"

    def __post_init__(self) -> None:
        if not self.prompt.strip():
            raise ValueError("Generation prompt cannot be empty")
        if self.response_schema is not None and not isinstance(self.response_schema, dict):
            raise ValueError("Generation response_schema must be a JSON Schema object")
        if not self.schema_name.strip():
            raise ValueError("Generation schema_name cannot be empty")


@dataclass(frozen=True, slots=True)
class GenerationResult:
    text: str
    provider: str
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BackendStatus:
    provider: str
    available: bool
    detail: str
    verified: bool = True


class AIBackend(Protocol):
    name: str

    def check(self) -> BackendStatus:
        """Check whether this backend can currently be used."""
        ...

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate text without writing project files."""
        ...
