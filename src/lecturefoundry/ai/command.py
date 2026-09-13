"""Safe subprocess utilities shared by CLI-based AI providers."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

from lecturefoundry.ai.base import AIBackendError, BackendStatus


Runner = Callable[..., subprocess.CompletedProcess[str]]
ExecutableFinder = Callable[[str], str | None]


class CommandBackend:
    name: str

    def __init__(
        self,
        *,
        command: str,
        timeout_seconds: float,
        runner: Runner = subprocess.run,
        executable_finder: ExecutableFinder = shutil.which,
    ) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds
        self._runner = runner
        self._executable_finder = executable_finder

    def check(self) -> BackendStatus:
        executable = self._executable_finder(self.command)
        if not executable:
            return BackendStatus(self.name, False, f"Command '{self.command}' was not found")
        return BackendStatus(self.name, True, f"Using {executable}")

    def _subprocess_environment(self, provider_names: Sequence[str]) -> dict[str, str]:
        safe_names = (
            "PATH",
            "HOME",
            "TMPDIR",
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "SSL_CERT_FILE",
            "SSL_CERT_DIR",
        )
        return {
            name: os.environ[name]
            for name in (*safe_names, *provider_names)
            if name in os.environ
        }

    def _run(
        self,
        arguments: Sequence[str],
        prompt: str,
        *,
        cwd: Path | None = None,
        environment_names: Sequence[str] = (),
    ) -> subprocess.CompletedProcess[str]:
        environment = self._subprocess_environment(environment_names)
        try:
            completed = self._runner(
                list(arguments),
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
                cwd=cwd,
                env=environment,
            )
        except FileNotFoundError as error:
            raise AIBackendError(f"Command '{self.command}' was not found") from error
        except subprocess.TimeoutExpired as error:
            raise AIBackendError(
                f"{self.name} timed out after {self.timeout_seconds:g} seconds"
            ) from error

        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            for name in environment_names:
                secret = environment.get(name)
                if secret and "KEY" in name.upper():
                    detail = detail.replace(secret, "[redacted]")
            if len(detail) > 2000:
                detail = f"{detail[:2000]}…"
            raise AIBackendError(f"{self.name} failed: {detail}")
        return completed
