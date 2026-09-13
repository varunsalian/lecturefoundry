"""Anthropic Claude Code CLI backend."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from coursera_lectures.ai.base import (
    AIBackendError,
    BackendStatus,
    GenerationRequest,
    GenerationResult,
)
from coursera_lectures.ai.command import CommandBackend, ExecutableFinder, Runner
from coursera_lectures.ai.prompting import combine_prompt
from coursera_lectures.ai.schema import schema_for_provider


class ClaudeCLIBackend(CommandBackend):
    name = "claude"

    def __init__(
        self,
        *,
        model: str | None = None,
        command: str = "claude",
        max_turns: int = 1,
        timeout_seconds: float = 600,
        runner: Runner | None = None,
        executable_finder: ExecutableFinder | None = None,
    ) -> None:
        kwargs = {}
        if runner is not None:
            kwargs["runner"] = runner
        if executable_finder is not None:
            kwargs["executable_finder"] = executable_finder
        super().__init__(command=command, timeout_seconds=timeout_seconds, **kwargs)
        if max_turns < 1:
            raise ValueError("Claude max_turns must be at least 1")
        self.model = model
        self.max_turns = max_turns

    def check(self) -> BackendStatus:
        installed = super().check()
        if not installed.available:
            return installed
        if os.environ.get("ANTHROPIC_API_KEY"):
            return BackendStatus(
                self.name,
                True,
                "Command found; API-key authentication configured but not network-verified",
                verified=False,
            )
        try:
            with TemporaryDirectory(prefix="coursera-lectures-claude-check-") as temp_dir:
                self._run(
                    [self.command, "auth", "status"],
                    "",
                    cwd=Path(temp_dir),
                    environment_names=("CLAUDE_CONFIG_DIR",),
                )
            return BackendStatus(
                self.name, True, "Command found and saved authentication is valid"
            )
        except AIBackendError as error:
            return BackendStatus(self.name, False, str(error))

    def generate(self, request: GenerationRequest) -> GenerationResult:
        with TemporaryDirectory(prefix="coursera-lectures-claude-") as temp_dir:
            working_dir = Path(temp_dir)
            arguments = [
                self.command,
                "--print",
                "--output-format",
                "text",
                "--no-session-persistence",
                "--safe-mode",
                "--restricted",
                "--strict-mcp-config",
                "--tools",
                "",
                "--permission-mode",
                "plan",
                "--permission-prompts",
                "none",
                "--disable-slash-commands",
                "--max-turns",
                str(self.max_turns),
            ]
            if self.model:
                arguments.extend(["--model", self.model])
            if request.response_schema is not None:
                arguments.extend(
                    [
                        "--json-schema",
                        json.dumps(
                            schema_for_provider(request.response_schema, self.name),
                            ensure_ascii=False,
                        ),
                    ]
                )

            completed = self._run(
                arguments,
                combine_prompt(request),
                cwd=working_dir,
                environment_names=(
                    "ANTHROPIC_API_KEY",
                    "CLAUDE_CONFIG_DIR",
                    "CLAUDE_CODE_USE_BEDROCK",
                    "CLAUDE_CODE_USE_VERTEX",
                    "CLAUDE_CODE_USE_FOUNDRY",
                    "AWS_PROFILE",
                    "AWS_REGION",
                    "AWS_DEFAULT_REGION",
                    "GOOGLE_APPLICATION_CREDENTIALS",
                ),
            )
            text = completed.stdout.strip()
        if not text:
            raise AIBackendError("Claude returned an empty response")
        return GenerationResult(
            text=text,
            provider=self.name,
            model=self.model,
            metadata={"model_selection": self.model or "claude-cli default"},
        )
