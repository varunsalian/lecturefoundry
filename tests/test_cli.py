from pathlib import Path

import coursera_lectures.cli as cli
from coursera_lectures.ai import BackendStatus
from coursera_lectures.cli import _uses_remote_service
from coursera_lectures.config import AISettings


def test_remote_notice_includes_agentic_cli_backends() -> None:
    assert _uses_remote_service("codex", {})
    assert _uses_remote_service("claude", {})


def test_local_ollama_does_not_get_remote_notice() -> None:
    assert not _uses_remote_service(
        "ollama", {"base_url": "http://localhost:11434"}
    )


def test_unverified_backend_check_is_not_reported_as_success(
    monkeypatch, capsys
) -> None:
    class Backend:
        def check(self) -> BackendStatus:
            return BackendStatus(
                "codex", True, "credential present but not verified", verified=False
            )

    monkeypatch.setattr(
        cli,
        "load_ai_settings",
        lambda *args, **kwargs: AISettings(provider="codex"),
    )
    monkeypatch.setattr(cli, "create_ai_backend", lambda settings: Backend())

    exit_code = cli.main(["ai", "check", "--config", str(Path("missing.toml"))])

    assert exit_code == 2
    assert capsys.readouterr().out.startswith("[CONFIGURED] codex:")
