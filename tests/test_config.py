from pathlib import Path

import pytest

from lecturefoundry.config import load_ai_settings


def test_loads_selected_provider_table(tmp_path: Path) -> None:
    config = tmp_path / "lecture.toml"
    config.write_text(
        """
[ai]
provider = "codex"
timeout_seconds = 42
system_prompt = "Generate HTML"

[ai.codex]
model = "example-model"
profile = "lecture"
""",
        encoding="utf-8",
    )

    settings = load_ai_settings(config)

    assert settings.provider == "codex"
    assert settings.model == "example-model"
    assert settings.timeout_seconds == 42
    assert settings.options["profile"] == "lecture"


def test_provider_and_model_can_be_overridden(tmp_path: Path) -> None:
    config = tmp_path / "lecture.toml"
    config.write_text(
        """
[ai]
provider = "ollama"
[ai.ollama]
model = "local-model"
[ai.claude]
model = "sonnet"
""",
        encoding="utf-8",
    )

    settings = load_ai_settings(
        config,
        provider_override="claude-cli",
        model_override="opus",
    )

    assert settings.provider == "claude"
    assert settings.model == "opus"


def test_rejects_unknown_provider(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported AI provider"):
        load_ai_settings(tmp_path / "missing.toml", provider_override="unknown")


def test_online_provider_cli_overrides_do_not_contain_key_value(tmp_path: Path) -> None:
    settings = load_ai_settings(
        tmp_path / "missing.toml",
        provider_override="openai-compatible",
        model_override="vendor-model",
        base_url_override="https://provider.example/v1",
        api_key_env_override="VENDOR_API_KEY",
    )

    assert settings.provider == "openai-compatible"
    assert settings.model == "vendor-model"
    assert settings.options["base_url"] == "https://provider.example/v1"
    assert settings.options["api_key_env"] == "VENDOR_API_KEY"


def test_rejects_literal_api_keys_in_config(tmp_path: Path) -> None:
    config = tmp_path / "lecture.toml"
    config.write_text(
        """
[ai]
provider = "openai"
[ai.openai]
model = "test-model"
api_key = "must-not-be-committed"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not allowed"):
        load_ai_settings(config)


def test_rejects_system_variable_as_api_key_source(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="system variable HOME"):
        load_ai_settings(
            tmp_path / "missing.toml",
            provider_override="openai",
            model_override="test-model",
            api_key_env_override="HOME",
        )


def test_rejects_invalid_configured_base_url(tmp_path: Path) -> None:
    config = tmp_path / "lecture.toml"
    config.write_text(
        """
[ai]
provider = "gemini"
[ai.gemini]
model = "example-model"
base_url = "not-a-url"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="absolute http"):
        load_ai_settings(config)


def test_rejects_literal_credentials_in_an_unselected_provider(tmp_path: Path) -> None:
    config = tmp_path / "lecture.toml"
    config.write_text(
        """
[ai]
provider = "ollama"
[ai.ollama]
model = "local"
[ai.openai]
api_key = "must-not-be-committed"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"\[ai.openai\].api_key"):
        load_ai_settings(config)


@pytest.mark.parametrize(
    "base_url",
    ["https://user@example.test/v1", "https://user:password@example.test/v1"],
)
def test_rejects_credentials_embedded_in_base_url(
    tmp_path: Path, base_url: str
) -> None:
    with pytest.raises(ValueError, match="embedded credentials"):
        load_ai_settings(
            tmp_path / "missing.toml",
            provider_override="openai",
            model_override="example-model",
            base_url_override=base_url,
        )


def test_rejects_credentials_in_an_unselected_provider_url(tmp_path: Path) -> None:
    config = tmp_path / "lecture.toml"
    config.write_text(
        """
[ai]
provider = "ollama"
[ai.ollama]
model = "local"
[ai.openai]
base_url = "https://user:password@example.test/v1"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="embedded credentials"):
        load_ai_settings(config)


def test_validates_every_environment_variable_option(tmp_path: Path) -> None:
    config = tmp_path / "lecture.toml"
    config.write_text(
        """
[ai]
provider = "openai"
[ai.openai]
model = "example-model"
organization_env = "HOME"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="system variable HOME"):
        load_ai_settings(config)
