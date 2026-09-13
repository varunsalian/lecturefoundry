"""Native OpenAI Responses API backend."""

from __future__ import annotations

from urllib.parse import quote

import requests

from coursera_lectures.ai.base import (
    AIBackendError,
    BackendStatus,
    GenerationRequest,
    GenerationResult,
)
from coursera_lectures.ai.http import APIKeyBackend, response_json
from coursera_lectures.ai.schema import prompt_with_schema, schema_for_provider


class OpenAIBackend(APIKeyBackend):
    name = "openai"

    def __init__(
        self,
        *,
        model: str | None,
        base_url: str = "https://api.openai.com/v1",
        api_key_env: str = "OPENAI_API_KEY",
        organization_env: str | None = None,
        project_env: str | None = None,
        timeout_seconds: float = 600,
        structured_output: bool = True,
        send_temperature: bool = False,
        max_output_tokens: int | None = None,
        session: requests.Session | None = None,
    ) -> None:
        super().__init__(
            model=model,
            base_url=base_url,
            api_key_env=api_key_env,
            timeout_seconds=timeout_seconds,
            session=session,
        )
        self.organization_env = organization_env
        self.project_env = project_env
        self.structured_output = structured_output
        self.send_temperature = send_temperature
        if max_output_tokens is not None and max_output_tokens < 1:
            raise ValueError("OpenAI max_output_tokens must be at least 1")
        self.max_output_tokens = max_output_tokens

    def _headers(self) -> dict[str, str]:
        import os

        headers = {
            "Authorization": f"Bearer {self._api_key()}",
            "Content-Type": "application/json",
        }
        if self.organization_env and os.environ.get(self.organization_env):
            headers["OpenAI-Organization"] = os.environ[self.organization_env]
        if self.project_env and os.environ.get(self.project_env):
            headers["OpenAI-Project"] = os.environ[self.project_env]
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
            "input": (
                request.prompt
                if self.structured_output
                else prompt_with_schema(request.prompt, request.response_schema)
            ),
            "store": False,
        }
        if request.system_prompt:
            payload["instructions"] = request.system_prompt
        if self.send_temperature and request.temperature is not None:
            payload["temperature"] = request.temperature
        if self.max_output_tokens is not None:
            payload["max_output_tokens"] = self.max_output_tokens
        if self.structured_output and request.response_schema is not None:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": request.schema_name,
                    "strict": True,
                    "schema": schema_for_provider(request.response_schema, self.name),
                }
            }

        try:
            response = self._session.post(
                f"{self.base_url}/responses",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            body = response_json(response, self.name)
        except requests.RequestException as error:
            raise AIBackendError(f"OpenAI request failed: {error}") from error

        status = body.get("status")
        if status is not None and status != "completed":
            error = body.get("error")
            incomplete = body.get("incomplete_details")
            detail = error or incomplete or "no details supplied"
            raise AIBackendError(f"OpenAI response status was {status}: {detail}")

        text = body.get("output_text")
        if not isinstance(text, str) or not text.strip():
            fragments = []
            refusals = []
            for item in body.get("output", []):
                if not isinstance(item, dict) or item.get("type") != "message":
                    continue
                for part in item.get("content", []):
                    if isinstance(part, dict) and part.get("type") == "output_text":
                        fragments.append(str(part.get("text", "")))
                    elif isinstance(part, dict) and part.get("type") == "refusal":
                        refusals.append(
                            str(part.get("refusal") or part.get("text") or "")
                        )
            text = "".join(fragments)
            if refusals and not text.strip():
                detail = "".join(refusals).strip() or "no details supplied"
                raise AIBackendError(f"OpenAI refused the response: {detail}")
        if not text.strip():
            raise AIBackendError("OpenAI returned no output text")

        return GenerationResult(
            text=text.strip(),
            provider=self.name,
            model=str(body.get("model") or model),
            metadata={key: body[key] for key in ("id", "status", "usage") if key in body}
            | (
                {"temperature_ignored": request.temperature}
                if request.temperature is not None and not self.send_temperature
                else {}
            ),
        )
