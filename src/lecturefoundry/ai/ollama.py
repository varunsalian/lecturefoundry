"""Ollama native HTTP API backend."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

import requests

from lecturefoundry.ai.base import (
    AIBackendError,
    BackendStatus,
    GenerationRequest,
    GenerationResult,
)
from lecturefoundry.ai.http import api_error_detail, response_json, retrying_session
from lecturefoundry.ai.schema import prompt_with_schema


class OllamaBackend:
    name = "ollama"

    def __init__(
        self,
        *,
        model: str | None,
        base_url: str = "http://localhost:11434",
        api_key_env: str | None = None,
        timeout_seconds: float = 600,
        structured_output: bool = True,
        session: requests.Session | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_base_url = (
            self.base_url if self.base_url.endswith("/api") else f"{self.base_url}/api"
        )
        self.api_key_env = api_key_env or None
        self.timeout_seconds = timeout_seconds
        self.structured_output = structured_output
        hostname = (urlparse(self.base_url).hostname or "").lower()
        self.cloud_host = hostname == "ollama.com" or hostname.endswith(".ollama.com")
        self._session = session or retrying_session()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key_env:
            api_key = os.environ.get(self.api_key_env)
            if not api_key:
                raise AIBackendError(
                    f"Environment variable {self.api_key_env} is required for Ollama"
                )
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def check(self) -> BackendStatus:
        try:
            response = self._session.get(
                f"{self.api_base_url}/tags",
                headers=self._headers(),
                timeout=min(self.timeout_seconds, 10),
            )
            body = response_json(response, self.name)
            models = {
                item.get("name")
                for item in body.get("models", [])
                if isinstance(item, dict) and item.get("name")
            }
        except (requests.RequestException, AIBackendError) as error:
            return BackendStatus(self.name, False, api_error_detail(error))

        if self.model and self.model not in models:
            return BackendStatus(
                self.name,
                False,
                f"Connected, but model '{self.model}' is not installed",
            )
        detail = f"Connected to {self.base_url}"
        if self.model:
            detail += f" with model {self.model}"
        return BackendStatus(self.name, True, detail)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        if not self.model:
            raise AIBackendError("An Ollama model must be configured")

        native_schema = self.structured_output and not self.cloud_host
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": (
                request.prompt
                if native_schema
                else prompt_with_schema(request.prompt, request.response_schema)
            ),
            "system": request.system_prompt,
            "stream": False,
            "think": False,
        }
        if request.temperature is not None:
            payload["options"] = {"temperature": request.temperature}
        if (
            native_schema
            and request.response_schema is not None
        ):
            payload["format"] = request.response_schema

        try:
            response = self._session.post(
                f"{self.api_base_url}/generate",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            body = response_json(response, self.name)
            text = str(body["response"])
        except requests.RequestException as error:
            raise AIBackendError(f"Ollama generation failed: {api_error_detail(error)}") from error
        except (KeyError, TypeError) as error:
            raise AIBackendError("Ollama response contained no generated text") from error

        if body.get("done") is False:
            raise AIBackendError("Ollama returned an incomplete non-streaming response")
        if body.get("done_reason") == "length":
            raise AIBackendError("Ollama stopped because the output limit was reached")
        if not text.strip():
            raise AIBackendError("Ollama returned empty generated text")

        metadata = {
            key: body[key]
            for key in (
                "done_reason",
                "total_duration",
                "prompt_eval_count",
                "eval_count",
            )
            if key in body
        }
        if self.structured_output and self.cloud_host and request.response_schema is not None:
            metadata["structured_output_native"] = False
        return GenerationResult(
            text=text.strip(),
            provider=self.name,
            model=self.model,
            metadata=metadata,
        )
