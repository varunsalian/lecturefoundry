"""OpenAI-compatible Chat Completions backend for third-party services."""

from __future__ import annotations

import requests

from coursera_lectures.ai.base import (
    AIBackendError,
    BackendStatus,
    GenerationRequest,
    GenerationResult,
)
from coursera_lectures.ai.http import APIKeyBackend, response_json
from coursera_lectures.ai.schema import prompt_with_schema, schema_for_provider


class OpenAICompatibleBackend(APIKeyBackend):
    name = "openai-compatible"

    def __init__(
        self,
        *,
        model: str | None,
        base_url: str,
        api_key_env: str = "OPENAI_COMPATIBLE_API_KEY",
        timeout_seconds: float = 600,
        structured_output: bool = True,
        max_tokens: int | None = None,
        session: requests.Session | None = None,
    ) -> None:
        super().__init__(
            model=model,
            base_url=base_url,
            api_key_env=api_key_env,
            timeout_seconds=timeout_seconds,
            session=session,
        )
        self.structured_output = structured_output
        if max_tokens is not None and max_tokens < 1:
            raise ValueError("OpenAI-compatible max_tokens must be at least 1")
        self.max_tokens = max_tokens

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        key = self._api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def check(self) -> BackendStatus:
        try:
            model = self._require_model()
            response = self._session.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=min(self.timeout_seconds, 15),
            )
            if getattr(response, "status_code", None) in {404, 405}:
                return BackendStatus(
                    self.name,
                    True,
                    f"Configured for model {model}; provider does not expose /models",
                    verified=False,
                )
            response_json(response, self.name)
            return BackendStatus(self.name, True, f"Connected with model {model}")
        except (requests.RequestException, AIBackendError) as error:
            return self._unavailable(error)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        model = self._require_model()
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        prompt = (
            request.prompt
            if self.structured_output
            else prompt_with_schema(request.prompt, request.response_schema)
        )
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, object] = {"model": model, "messages": messages}
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if self.structured_output and request.response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "strict": True,
                    "schema": schema_for_provider(request.response_schema, self.name),
                },
            }

        try:
            response = self._session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            body = response_json(response, self.name)
            choice = body["choices"][0]
            content = choice["message"]["content"]
        except requests.RequestException as error:
            raise AIBackendError(f"OpenAI-compatible request failed: {error}") from error
        except (KeyError, IndexError, TypeError) as error:
            raise AIBackendError("OpenAI-compatible response contained no message") from error

        finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
        if finish_reason not in {None, "stop"}:
            raise AIBackendError(
                f"OpenAI-compatible provider did not complete the response: {finish_reason}"
            )

        if isinstance(content, list):
            text = "".join(
                str(part.get("text", ""))
                for part in content
                if isinstance(part, dict) and part.get("type") in {"text", "output_text"}
            )
        else:
            text = str(content)
        if not text.strip():
            raise AIBackendError("OpenAI-compatible response contained empty text")
        return GenerationResult(
            text=text.strip(),
            provider=self.name,
            model=str(body.get("model") or model),
            metadata={key: body[key] for key in ("id", "usage") if key in body}
            | ({"finish_reason": finish_reason} if finish_reason is not None else {}),
        )
