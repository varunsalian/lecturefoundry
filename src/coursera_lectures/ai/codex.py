"""OpenAI Codex CLI backend."""

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


class CodexCLIBackend(CommandBackend):
    name = "codex"

    def __init__(
        self,
        *,
        model: str | None = None,
        command: str = "codex",
        profile: str | None = None,
        allow_agentic_file_reads: bool = False,
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
        self.model = model
        if profile:
            raise ValueError(
                "Codex profiles are disabled for isolated generation; configure the model directly"
            )
        self.allow_agentic_file_reads = allow_agentic_file_reads

    def check(self) -> BackendStatus:
        installed = super().check()
        if not installed.available:
            return installed
        if not self.allow_agentic_file_reads:
            return BackendStatus(
                self.name,
                False,
                "Agentic file inspection is disabled; set "
                "[ai.codex].allow_agentic_file_reads=true only for trusted transcripts",
            )
        if os.environ.get("CODEX_API_KEY") or os.environ.get("OPENAI_API_KEY"):
            return BackendStatus(
                self.name,
                True,
                "Command found; API-key authentication configured but not network-verified",
                verified=False,
            )
        try:
            with TemporaryDirectory(prefix="coursera-lectures-codex-check-") as temp_dir:
                self._run(
                    [self.command, "login", "status"],
                    "",
                    cwd=Path(temp_dir),
                    environment_names=("CODEX_HOME",),
                )
            return BackendStatus(
                self.name, True, "Command found and saved authentication is valid"
            )
        except AIBackendError as error:
            return BackendStatus(self.name, False, str(error))

    def generate(self, request: GenerationRequest) -> GenerationResult:
        if not self.allow_agentic_file_reads:
            raise AIBackendError(
                "Codex CLI generation is disabled because its read-only sandbox can inspect "
                "files. Set [ai.codex].allow_agentic_file_reads=true only for trusted "
                "transcripts, or use the tool-free OpenAI API backend."
            )
        with TemporaryDirectory(prefix="coursera-lectures-codex-") as temp_dir:
            working_dir = Path(temp_dir)
            output_path = working_dir / "result.txt"
            arguments = [
                self.command,
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--config",
                "shell_environment_policy.inherit=none",
                "--config",
                'approval_policy="never"',
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--cd",
                str(working_dir),
                "--color",
                "never",
                "--output-last-message",
                str(output_path),
            ]
            if self.model:
                arguments.extend(["--model", self.model])
            if request.response_schema is not None:
                schema_path = working_dir / "response-schema.json"
                schema_path.write_text(
                    json.dumps(
                        schema_for_provider(request.response_schema, self.name),
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                arguments.extend(["--output-schema", str(schema_path)])
            arguments.append("-")

            completed = self._run(
                arguments,
                combine_prompt(request),
                cwd=working_dir,
                environment_names=("CODEX_HOME", "CODEX_API_KEY", "OPENAI_API_KEY"),
            )
            if not output_path.exists():
                raise AIBackendError(
                    f"Codex completed without creating its output file: {completed.stdout.strip()}"
                )
            text = output_path.read_text(encoding="utf-8").strip()

        if not text:
            raise AIBackendError("Codex returned an empty response")
        return GenerationResult(
            text=text,
            provider=self.name,
            model=self.model,
            metadata={"model_selection": self.model or "codex-cli default"},
        )
