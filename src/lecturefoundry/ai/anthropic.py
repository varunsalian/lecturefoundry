"""Native Anthropic Messages API backend."""

from __future__ import annotations

import os
from urllib.parse import quote

import requests

from lecturefoundry.ai.base import (
    AIBackendError,
    BackendStatus,
    GenerationRequest,
    GenerationResult,
)
from lecturefoundry.ai.http import APIKeyBackend, response_json
from lecturefoundry.ai.schema import prompt_with_schema, schema_for_provider


class AnthropicBackend(APIKeyBackend):
    name = "anthropic"

    def __init__(
        self,
        *,
        model: str | None,
        base_url: str = "https://api.anthropic.com/v1",
        api_key_env: str = "ANTHROPIC_API_KEY",
        workspace_env: str | None = None,
        api_version: str = "2023-06-01",
        max_tokens: int = 4096,
        structured_output: bool = True,
        send_temperature: bool = False,
        timeout_seconds: float = 600,
        session: requests.Session | None = None,
    ) -> None:
        super().__init__(
            model=model,
            base_url=base_url,
            api_key_env=api_key_env,
            timeout_seconds=timeout_seconds,
            session=session,
        )
        if max_tokens < 1:
            raise ValueError("Anthropic max_tokens must be at least 1")
        self.workspace_env = workspace_env
        self.api_version = api_version
        self.max_tokens = max_tokens
        self.structured_output = structured_output
        self.send_temperature = send_temperature

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key()}",
            "anthropic-version": self.api_version,
            "Content-Type": "application/json",
        }
        if self.workspace_env and os.environ.get(self.workspace_env):
            headers["anthropic-workspace-id"] = os.environ[self.workspace_env]
        return headers

    def check(self) -> BackendStatus:
        try:
            model = self._require_model()
            response = self._session.get(
                f"{self.base_url}/models/{quote(model, safe='')}",
                headers=self._headers(),
                timeout=min(self.timeout_seconds, 15),
            )
            response_json(response, self.name)
            return BackendStatus(self.name, True, f"Connected with model {model}")
        except (requests.RequestException, AIBackendError) as error:
            return self._unavailable(error)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        model = self._require_model()
        payload: dict[str, object] = {
            "model": model,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        request.prompt
                        if self.structured_output
                        else prompt_with_schema(request.prompt, request.response_schema)
                    ),
                }
            ],
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt
        if self.structured_output and request.response_schema is not None:
            payload["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": schema_for_provider(request.response_schema, self.name),
                }
            }
        if self.send_temperature and request.temperature is not None:
            payload["temperature"] = request.temperature

        try:
            response = self._session.post(
                f"{self.base_url}/messages",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            body = response_json(response, self.name)
        except requests.RequestException as error:
            raise AIBackendError(f"Anthropic request failed: {error}") from error

        fragments = [
            str(part.get("text", ""))
            for part in body.get("content", [])
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        text = "".join(fragments).strip()
        stop_reason = body.get("stop_reason")
        stop_details = body.get("stop_details")
        if stop_reason not in {None, "end_turn", "stop_sequence"} or (
            isinstance(stop_details, dict) and stop_details.get("type") == "refusal"
        ):
            raise AIBackendError(
                f"Anthropic did not complete the response: {stop_details or stop_reason}"
            )
        if not text:
            raise AIBackendError("Anthropic returned no text content")
        return GenerationResult(
            text=text,
            provider=self.name,
            model=str(body.get("model") or model),
            metadata={
                key: body[key]
                for key in ("id", "stop_reason", "stop_details", "usage")
                if key in body
            }
            | (
                {"temperature_ignored": request.temperature}
                if request.temperature is not None and not self.send_temperature
                else {}
            ),
        )
