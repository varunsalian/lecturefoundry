"""Construct AI backends from project settings."""

from coursera_lectures.ai.base import AIBackend
from coursera_lectures.ai.anthropic import AnthropicBackend
from coursera_lectures.ai.claude import ClaudeCLIBackend
from coursera_lectures.ai.codex import CodexCLIBackend
from coursera_lectures.ai.gemini import GeminiBackend
from coursera_lectures.ai.ollama import OllamaBackend
from coursera_lectures.ai.openai import OpenAIBackend
from coursera_lectures.ai.openai_compatible import OpenAICompatibleBackend
from coursera_lectures.config import AISettings


def _optional(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _boolean(value: object, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise ValueError("Boolean AI options must be true or false")


def create_ai_backend(settings: AISettings) -> AIBackend:
    options = settings.options

    if settings.provider == "ollama":
        return OllamaBackend(
            model=settings.model,
            base_url=str(options.get("base_url", "http://localhost:11434")),
            api_key_env=_optional(options.get("api_key_env")),
            structured_output=_boolean(options.get("structured_output")),
            timeout_seconds=settings.timeout_seconds,
        )
    if settings.provider == "codex":
        return CodexCLIBackend(
            model=settings.model,
            command=str(options.get("command", "codex")),
            profile=_optional(options.get("profile")),
            allow_agentic_file_reads=_boolean(
                options.get("allow_agentic_file_reads"), default=False
            ),
            timeout_seconds=settings.timeout_seconds,
        )
    if settings.provider == "claude":
        return ClaudeCLIBackend(
            model=settings.model,
            command=str(options.get("command", "claude")),
            max_turns=int(options.get("max_turns", 1)),
            timeout_seconds=settings.timeout_seconds,
        )
    if settings.provider == "openai":
        return OpenAIBackend(
            model=settings.model,
            base_url=str(options.get("base_url", "https://api.openai.com/v1")),
            api_key_env=str(options.get("api_key_env", "OPENAI_API_KEY")),
            organization_env=_optional(options.get("organization_env")),
            project_env=_optional(options.get("project_env")),
            structured_output=_boolean(options.get("structured_output")),
            send_temperature=_boolean(options.get("send_temperature"), default=False),
            max_output_tokens=(
                int(options["max_output_tokens"])
                if options.get("max_output_tokens") is not None
                else None
            ),
            timeout_seconds=settings.timeout_seconds,
        )
    if settings.provider == "openai-compatible":
        return OpenAICompatibleBackend(
            model=settings.model,
            base_url=str(options.get("base_url", "https://api.openai.com/v1")),
            api_key_env=str(options.get("api_key_env", "OPENAI_COMPATIBLE_API_KEY")),
            structured_output=_boolean(options.get("structured_output")),
            max_tokens=(
                int(options["max_tokens"])
                if options.get("max_tokens") is not None
                else None
            ),
            timeout_seconds=settings.timeout_seconds,
        )
    if settings.provider == "anthropic":
        return AnthropicBackend(
            model=settings.model,
            base_url=str(options.get("base_url", "https://api.anthropic.com/v1")),
            api_key_env=str(options.get("api_key_env", "ANTHROPIC_API_KEY")),
            workspace_env=_optional(options.get("workspace_env")),
            api_version=str(options.get("api_version", "2023-06-01")),
            max_tokens=int(options.get("max_tokens", 4096)),
            structured_output=_boolean(options.get("structured_output")),
            send_temperature=_boolean(options.get("send_temperature"), default=False),
            timeout_seconds=settings.timeout_seconds,
        )
    if settings.provider == "gemini":
        return GeminiBackend(
            model=settings.model,
            base_url=str(
                options.get(
                    "base_url",
                    "https://generativelanguage.googleapis.com/v1beta",
                )
            ),
            api_key_env=str(options.get("api_key_env", "GEMINI_API_KEY")),
            structured_output=_boolean(options.get("structured_output")),
            max_output_tokens=(
                int(options["max_output_tokens"])
                if options.get("max_output_tokens") is not None
                else None
            ),
            timeout_seconds=settings.timeout_seconds,
        )
    raise ValueError(f"Unsupported AI provider: {settings.provider}")
