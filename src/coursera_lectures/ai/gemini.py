"""Native Google Gemini generateContent API backend."""

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


class GeminiBackend(APIKeyBackend):
    name = "gemini"

    def __init__(
        self,
        *,
        model: str | None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        api_key_env: str = "GEMINI_API_KEY",
        timeout_seconds: float = 600,
        structured_output: bool = True,
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
        self.structured_output = structured_output
        if max_output_tokens is not None and max_output_tokens < 1:
            raise ValueError("Gemini max_output_tokens must be at least 1")
        self.max_output_tokens = max_output_tokens

    def _model_name(self) -> str:
        return self._require_model().removeprefix("models/")

    def _headers(self) -> dict[str, str]:
        return {
            "x-goog-api-key": self._api_key(),
            "Content-Type": "application/json",
        }

    def check(self) -> BackendStatus:
        try:
            model = self._model_name()
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
        model = self._model_name()
        prompt = (
            request.prompt
            if self.structured_output
            else prompt_with_schema(request.prompt, request.response_schema)
        )
        payload: dict[str, object] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}]
        }
        if request.system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": request.system_prompt}]}
        generation_config: dict[str, object] = {}
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if self.max_output_tokens is not None:
            generation_config["maxOutputTokens"] = self.max_output_tokens
        if self.structured_output and request.response_schema is not None:
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseJsonSchema"] = schema_for_provider(
                request.response_schema, self.name
            )
        if generation_config:
            payload["generationConfig"] = generation_config

        try:
            response = self._session.post(
                f"{self.base_url}/models/{quote(model, safe='')}:generateContent",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            body = response_json(response, self.name)
            candidate = body["candidates"][0]
            parts = candidate["content"]["parts"]
        except requests.RequestException as error:
            raise AIBackendError(f"Gemini request failed: {error}") from error
        except (KeyError, IndexError, TypeError) as error:
            prompt_feedback = body.get("promptFeedback")
            block_reason = (
                prompt_feedback.get("blockReason")
                if isinstance(prompt_feedback, dict)
                else None
            )
            detail = f": prompt blocked ({block_reason})" if block_reason else ""
            raise AIBackendError(f"Gemini response contained no candidate text{detail}") from error

        finish_reason = candidate.get("finishReason") if isinstance(candidate, dict) else None
        if finish_reason is not None and finish_reason != "STOP":
            raise AIBackendError(f"Gemini did not complete the response: {finish_reason}")

        text = "".join(
            str(part.get("text", "")) for part in parts if isinstance(part, dict)
        ).strip()
        if not text:
            raise AIBackendError("Gemini response contained empty text")
        return GenerationResult(
            text=text,
            provider=self.name,
            model=model,
            metadata={
                key: body[key]
                for key in ("usageMetadata", "modelVersion", "responseId", "promptFeedback")
                if key in body
            }
            | ({"finishReason": finish_reason} if finish_reason is not None else {}),
        )
