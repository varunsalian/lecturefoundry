"""Project configuration with backend-specific AI options."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib


PROVIDER_ALIASES = {
    "ollama": "ollama",
    "codex": "codex",
    "codex-cli": "codex",
    "claude": "claude",
    "claude-cli": "claude",
    "openai": "openai",
    "openai-api": "openai",
    "openai-compatible": "openai-compatible",
    "openai_compatible": "openai-compatible",
    "anthropic": "anthropic",
    "anthropic-api": "anthropic",
    "gemini": "gemini",
    "google": "gemini",
    "google-gemini": "gemini",
}

SUPPORTED_PROVIDERS = (
    "ollama",
    "codex",
    "claude",
    "openai",
    "openai-compatible",
    "anthropic",
    "gemini",
)


@dataclass(frozen=True, slots=True)
class AISettings:
    provider: str
    model: str | None = None
    timeout_seconds: float = 600
    system_prompt: str = ""
    options: dict[str, Any] = field(default_factory=dict)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DISALLOWED_CREDENTIAL_ENV_NAMES = {"HOME", "PATH", "SHELL", "USER", "PWD"}


def _validate_environment_name(value: object, option: str) -> str:
    name = str(value).strip()
    if not _ENVIRONMENT_NAME.fullmatch(name):
        raise ValueError(f"{option} must be a valid environment-variable name")
    if name in _DISALLOWED_CREDENTIAL_ENV_NAMES:
        raise ValueError(f"{option} cannot use the system variable {name}")
    return name


def _validate_base_url(value: object, option: str) -> str:
    base_url = str(value).strip()
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{option} must be an absolute http:// or https:// URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{option} cannot contain embedded credentials")
    if parsed.query or parsed.fragment:
        raise ValueError(f"{option} cannot contain a query string or fragment")
    return base_url


def _validate_provider_tables(ai_data: dict[str, Any]) -> None:
    forbidden_keys = {
        "api_key",
        "apikey",
        "access_token",
        "auth_token",
        "token",
        "secret",
        "password",
    }
    for table_name, table in ai_data.items():
        if not isinstance(table, dict):
            continue
        exposed = forbidden_keys.intersection(str(key).lower() for key in table)
        if exposed:
            name = sorted(exposed)[0]
            raise ValueError(
                f"[ai.{table_name}].{name} is not allowed; store credentials in an "
                "environment variable and configure api_key_env"
            )
        if "base_url" in table:
            _validate_base_url(table["base_url"], f"[ai.{table_name}].base_url")
        for option_name, option_value in table.items():
            if option_name.endswith("_env") and _optional_string(option_value):
                _validate_environment_name(
                    option_value, f"[ai.{table_name}].{option_name}"
                )


def load_ai_settings(
    path: Path,
    *,
    provider_override: str | None = None,
    model_override: str | None = None,
    base_url_override: str | None = None,
    api_key_env_override: str | None = None,
) -> AISettings:
    """Load AI settings and apply safe command-line overrides."""

    data: dict[str, Any] = {}
    if path.exists():
        with path.open("rb") as config_file:
            data = tomllib.load(config_file)

    ai_data = data.get("ai", {})
    if not isinstance(ai_data, dict):
        raise ValueError("[ai] must be a TOML table")
    _validate_provider_tables(ai_data)
    requested_provider = provider_override or ai_data.get("provider", "ollama")
    provider = PROVIDER_ALIASES.get(str(requested_provider).lower())
    if provider is None:
        supported = ", ".join(sorted(PROVIDER_ALIASES))
        raise ValueError(f"Unsupported AI provider '{requested_provider}'. Choose: {supported}")

    provider_data = ai_data.get(provider, {})
    if not isinstance(provider_data, dict):
        raise ValueError(f"[ai.{provider}] must be a TOML table")
    timeout_seconds = float(ai_data.get("timeout_seconds", 600))
    if timeout_seconds <= 0:
        raise ValueError("ai.timeout_seconds must be greater than zero")

    model = _optional_string(model_override) or _optional_string(
        provider_data.get("model")
    )
    options = dict(provider_data)
    if "base_url" in options:
        options["base_url"] = _validate_base_url(
            options["base_url"], f"[ai.{provider}].base_url"
        )
    for option_name, option_value in tuple(options.items()):
        if option_name.endswith("_env") and _optional_string(option_value):
            options[option_name] = _validate_environment_name(
                option_value, f"[ai.{provider}].{option_name}"
            )
    if base_url_override is not None:
        options["base_url"] = _validate_base_url(base_url_override, "--base-url")
    if api_key_env_override is not None:
        options["api_key_env"] = _validate_environment_name(
            api_key_env_override, "--api-key-env"
        )

    return AISettings(
        provider=provider,
        model=model,
        timeout_seconds=timeout_seconds,
        system_prompt=str(ai_data.get("system_prompt", "")).strip(),
        options=options,
    )
