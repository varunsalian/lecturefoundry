import os

import pytest

from coursera_lectures.ai import AIBackendError, GenerationRequest
from coursera_lectures.ai.anthropic import AnthropicBackend
from coursera_lectures.ai.gemini import GeminiBackend
from coursera_lectures.ai.openai import OpenAIBackend
from coursera_lectures.ai.openai_compatible import OpenAICompatibleBackend
from coursera_lectures.lesson import lesson_content_schema


class FakeResponse:
    status_code = 200

    def __init__(self, body: dict) -> None:
        self.body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.body


class FakeSession:
    def __init__(self, body: dict) -> None:
        self.body = body
        self.calls: list[tuple[str, str, dict]] = []

    def get(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(("GET", url, kwargs))
        return FakeResponse({"id": "model"})

    def post(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(("POST", url, kwargs))
        return FakeResponse(self.body)


def test_openai_uses_responses_api(monkeypatch) -> None:
    monkeypatch.setenv("TEST_OPENAI_KEY", "secret")
    session = FakeSession(
        {
            "id": "resp_1",
            "model": "test-model",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "result"}],
                }
            ],
            "usage": {"total_tokens": 10},
        }
    )
    backend = OpenAIBackend(
        model="test-model",
        api_key_env="TEST_OPENAI_KEY",
        session=session,
    )

    result = backend.generate(
        GenerationRequest(
            prompt="Task",
            system_prompt="Rules",
            temperature=0.2,
            response_schema=lesson_content_schema(),
            schema_name="lecture_lesson",
        )
    )

    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url == "https://api.openai.com/v1/responses"
    assert kwargs["headers"]["Authorization"] == "Bearer secret"
    assert kwargs["json"]["instructions"] == "Rules"
    assert kwargs["json"]["store"] is False
    assert "temperature" not in kwargs["json"]
    assert kwargs["json"]["text"]["format"]["type"] == "json_schema"
    assert kwargs["json"]["text"]["format"]["strict"] is True
    sent_schema = kwargs["json"]["text"]["format"]["schema"]
    assert "minLength" not in sent_schema["properties"]["title"]
    assert "minItems" not in sent_schema["properties"]["sections"]
    assert result.text == "result"
    assert result.metadata["temperature_ignored"] == 0.2


def test_openai_compatible_uses_chat_completions(monkeypatch) -> None:
    monkeypatch.setenv("ROUTER_KEY", "secret")
    session = FakeSession(
        {
            "id": "chat_1",
            "model": "vendor-model",
            "choices": [{"message": {"content": "compatible result"}}],
        }
    )
    backend = OpenAICompatibleBackend(
        model="vendor-model",
        base_url="https://provider.example/v1/",
        api_key_env="ROUTER_KEY",
        session=session,
    )

    result = backend.generate(
        GenerationRequest(
            prompt="Task",
            system_prompt="Rules",
            response_schema=lesson_content_schema(),
        )
    )

    _, url, kwargs = session.calls[0]
    assert url == "https://provider.example/v1/chat/completions"
    assert kwargs["json"]["messages"][0] == {"role": "system", "content": "Rules"}
    assert kwargs["json"]["response_format"]["type"] == "json_schema"
    assert result.text == "compatible result"


def test_openai_compatible_marks_missing_models_endpoint_unverified(monkeypatch) -> None:
    monkeypatch.setenv("ROUTER_KEY", "secret")

    class ModelsUnavailableSession(FakeSession):
        def get(self, url: str, **kwargs) -> FakeResponse:
            response = FakeResponse({})
            response.status_code = 404
            return response

    backend = OpenAICompatibleBackend(
        model="vendor-model",
        base_url="https://provider.example/v1",
        api_key_env="ROUTER_KEY",
        session=ModelsUnavailableSession({}),
    )

    status = backend.check()

    assert status.available
    assert not status.verified


def test_prompt_contains_schema_when_native_structured_output_is_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setenv("TEST_OPENAI_KEY", "secret")
    session = FakeSession({"status": "completed", "output_text": "result"})
    backend = OpenAIBackend(
        model="test-model",
        api_key_env="TEST_OPENAI_KEY",
        structured_output=False,
        session=session,
    )

    backend.generate(
        GenerationRequest(prompt="Task", response_schema=lesson_content_schema())
    )

    payload = session.calls[0][2]["json"]
    assert "text" not in payload
    assert "Required JSON Schema" in payload["input"]


def test_anthropic_uses_messages_api(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_KEY", "secret")
    session = FakeSession(
        {
            "id": "msg_1",
            "model": "test-claude",
            "content": [{"type": "text", "text": "anthropic result"}],
            "stop_reason": "end_turn",
        }
    )
    backend = AnthropicBackend(
        model="test-claude",
        api_key_env="CLAUDE_KEY",
        session=session,
    )

    result = backend.generate(
        GenerationRequest(
            prompt="Task",
            system_prompt="Rules",
            temperature=0.2,
            response_schema=lesson_content_schema(),
        )
    )

    _, url, kwargs = session.calls[0]
    assert url == "https://api.anthropic.com/v1/messages"
    assert kwargs["headers"]["Authorization"] == "Bearer secret"
    assert kwargs["headers"]["anthropic-version"] == "2023-06-01"
    assert kwargs["json"]["system"] == "Rules"
    assert "temperature" not in kwargs["json"]
    assert kwargs["json"]["output_config"]["format"]["type"] == "json_schema"
    sent_schema = kwargs["json"]["output_config"]["format"]["schema"]
    assert "minLength" not in sent_schema["properties"]["title"]
    assert result.text == "anthropic result"


def test_gemini_uses_generate_content_api(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_KEY", "secret")
    session = FakeSession(
        {
            "candidates": [
                {"content": {"parts": [{"text": "gemini "}, {"text": "result"}]}}
            ],
            "usageMetadata": {"totalTokenCount": 9},
        }
    )
    backend = GeminiBackend(
        model="models/test-gemini",
        api_key_env="GOOGLE_KEY",
        session=session,
    )

    result = backend.generate(
        GenerationRequest(
            prompt="Task",
            system_prompt="Rules",
            response_schema=lesson_content_schema(),
        )
    )

    _, url, kwargs = session.calls[0]
    assert url.endswith("/models/test-gemini:generateContent")
    assert kwargs["headers"]["x-goog-api-key"] == "secret"
    assert kwargs["json"]["systemInstruction"]["parts"][0]["text"] == "Rules"
    assert kwargs["json"]["generationConfig"]["responseMimeType"] == "application/json"
    assert kwargs["json"]["generationConfig"]["responseJsonSchema"]["type"] == "object"
    sent_schema = kwargs["json"]["generationConfig"]["responseJsonSchema"]
    assert "minLength" not in sent_schema["properties"]["title"]
    assert result.text == "gemini result"


def test_anthropic_projects_unsupported_collection_limits(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_KEY", "secret")
    session = FakeSession(
        {
            "content": [{"type": "text", "text": "result"}],
            "stop_reason": "end_turn",
        }
    )
    backend = AnthropicBackend(
        model="test-claude", api_key_env="CLAUDE_KEY", session=session
    )

    backend.generate(
        GenerationRequest(
            prompt="Task",
            response_schema=lesson_content_schema(min_sections=4, max_sections=4),
        )
    )

    sections = session.calls[0][2]["json"]["output_config"]["format"]["schema"][
        "properties"
    ]["sections"]
    assert "minItems" not in sections
    assert "maxItems" not in sections


def test_openai_rejects_an_incomplete_response(monkeypatch) -> None:
    monkeypatch.setenv("TEST_OPENAI_KEY", "secret")
    backend = OpenAIBackend(
        model="test-model",
        api_key_env="TEST_OPENAI_KEY",
        session=FakeSession(
            {
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "output_text": "partial",
            }
        ),
    )

    with pytest.raises(AIBackendError, match="status was incomplete"):
        backend.generate(GenerationRequest(prompt="Task"))


def test_openai_surfaces_a_structured_refusal(monkeypatch) -> None:
    monkeypatch.setenv("TEST_OPENAI_KEY", "secret")
    backend = OpenAIBackend(
        model="test-model",
        api_key_env="TEST_OPENAI_KEY",
        session=FakeSession(
            {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "refusal", "refusal": "request declined"}
                        ],
                    }
                ],
            }
        ),
    )

    with pytest.raises(AIBackendError, match="request declined"):
        backend.generate(GenerationRequest(prompt="Task"))


def test_anthropic_rejects_truncated_output(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_KEY", "secret")
    backend = AnthropicBackend(
        model="test-claude",
        api_key_env="CLAUDE_KEY",
        session=FakeSession(
            {
                "content": [{"type": "text", "text": "partial"}],
                "stop_reason": "max_tokens",
            }
        ),
    )

    with pytest.raises(AIBackendError, match="did not complete"):
        backend.generate(GenerationRequest(prompt="Task"))


def test_anthropic_rejects_other_nonterminal_stop_reasons(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_KEY", "secret")
    backend = AnthropicBackend(
        model="test-claude",
        api_key_env="CLAUDE_KEY",
        session=FakeSession(
            {
                "content": [{"type": "text", "text": "partial"}],
                "stop_reason": "pause_turn",
            }
        ),
    )

    with pytest.raises(AIBackendError, match="pause_turn"):
        backend.generate(GenerationRequest(prompt="Task"))


def test_gemini_reports_blocked_completion(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_KEY", "secret")
    backend = GeminiBackend(
        model="test-gemini",
        api_key_env="GOOGLE_KEY",
        session=FakeSession(
            {
                "candidates": [
                    {
                        "finishReason": "SAFETY",
                        "content": {"parts": [{"text": "partial"}]},
                    }
                ]
            }
        ),
    )

    with pytest.raises(AIBackendError, match="SAFETY"):
        backend.generate(GenerationRequest(prompt="Task"))


def test_gemini_handles_null_prompt_feedback(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_KEY", "secret")
    backend = GeminiBackend(
        model="test-gemini",
        api_key_env="GOOGLE_KEY",
        session=FakeSession({"promptFeedback": None, "candidates": []}),
    )

    with pytest.raises(AIBackendError, match="no candidate text"):
        backend.generate(GenerationRequest(prompt="Task"))


def test_online_backend_check_reports_missing_key() -> None:
    os.environ.pop("DEFINITELY_MISSING_KEY", None)
    backend = OpenAIBackend(
        model="test-model",
        api_key_env="DEFINITELY_MISSING_KEY",
        session=FakeSession({}),
    )

    status = backend.check()

    assert not status.available
    assert "DEFINITELY_MISSING_KEY" in status.detail
