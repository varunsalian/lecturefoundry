import json
import subprocess
from pathlib import Path

import pytest

from lecturefoundry.ai.base import AIBackendError, GenerationRequest
from lecturefoundry.ai.claude import ClaudeCLIBackend
from lecturefoundry.ai.codex import CodexCLIBackend
from lecturefoundry.ai.http import retrying_session
from lecturefoundry.ai.ollama import OllamaBackend
from lecturefoundry.ai.schema import schema_for_provider
from lecturefoundry.lesson import lesson_content_schema


class FakeResponse:
    def __init__(self, body: dict) -> None:
        self.body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.body


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []

    def get(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(("GET", url, kwargs))
        return FakeResponse({"models": [{"name": "test-model"}]})

    def post(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append(("POST", url, kwargs))
        return FakeResponse(
            {
                "response": "<html>ok</html>",
                "done_reason": "stop",
                "eval_count": 5,
            }
        )


def test_ollama_uses_non_streaming_generate_api() -> None:
    session = FakeSession()
    backend = OllamaBackend(model="test-model", session=session)

    result = backend.generate(
        GenerationRequest(
            prompt="Build it",
            system_prompt="Return HTML",
            temperature=0.2,
            response_schema=lesson_content_schema(),
        )
    )

    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url.endswith("/api/generate")
    assert kwargs["json"]["stream"] is False
    assert kwargs["json"]["think"] is False
    assert kwargs["json"]["options"] == {"temperature": 0.2}
    assert kwargs["json"]["format"]["type"] == "object"
    assert result.text == "<html>ok</html>"


def test_ollama_check_validates_configured_model() -> None:
    backend = OllamaBackend(model="missing", session=FakeSession())

    status = backend.check()

    assert not status.available
    assert "not installed" in status.detail


def test_ollama_accepts_documented_api_base_url() -> None:
    session = FakeSession()
    backend = OllamaBackend(
        model="test-model", base_url="https://ollama.com/api", session=session
    )

    backend.generate(GenerationRequest(prompt="Build it"))

    assert session.calls[0][1] == "https://ollama.com/api/generate"


def test_ollama_cloud_uses_prompt_json_and_local_validation() -> None:
    session = FakeSession()
    backend = OllamaBackend(
        model="test-model", base_url="https://ollama.com", session=session
    )

    result = backend.generate(
        GenerationRequest(prompt="Build it", response_schema=lesson_content_schema())
    )

    assert "format" not in session.calls[0][2]["json"]
    assert "Required JSON Schema" in session.calls[0][2]["json"]["prompt"]
    assert result.metadata["structured_output_native"] is False


def test_codex_reads_final_message_file(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setenv("COURSERA_CAUTH", "must-not-leak")

    def runner(arguments, **kwargs):
        captured["arguments"] = arguments
        captured["prompt"] = kwargs["input"]
        captured["environment"] = kwargs["env"]
        captured["cwd"] = kwargs["cwd"]
        schema_path = Path(arguments[arguments.index("--output-schema") + 1])
        captured["schema"] = json.loads(schema_path.read_text(encoding="utf-8"))
        output_path = Path(arguments[arguments.index("--output-last-message") + 1])
        output_path.write_text("<html>codex</html>", encoding="utf-8")
        return subprocess.CompletedProcess(arguments, 0, stdout="events", stderr="")

    backend = CodexCLIBackend(
        model="test-model", runner=runner, allow_agentic_file_reads=True
    )
    result = backend.generate(
        GenerationRequest(
            prompt="Build it",
            system_prompt="Return only HTML",
            response_schema=lesson_content_schema(
                min_sections=3,
                max_sections=5,
                min_examples=2,
                max_examples=4,
                min_questions=3,
                max_questions=3,
            ),
        )
    )

    assert captured["arguments"][:2] == ["codex", "exec"]
    assert "--ephemeral" in captured["arguments"]
    assert "--ignore-user-config" in captured["arguments"]
    assert "--output-schema" in captured["arguments"]
    assert 'approval_policy="never"' in captured["arguments"]
    assert "minLength" not in captured["schema"]["properties"]["title"]
    assert captured["schema"]["properties"]["sections"]["minItems"] == 3
    assert captured["schema"]["properties"]["sections"]["maxItems"] == 5
    assert captured["schema"]["properties"]["examples"]["minItems"] == 2
    assert captured["schema"]["properties"]["review_questions"]["maxItems"] == 3
    assert ["--sandbox", "read-only"] == captured["arguments"][
        captured["arguments"].index("--sandbox") :
        captured["arguments"].index("--sandbox") + 2
    ]
    assert "System instructions:" in captured["prompt"]
    assert "COURSERA_CAUTH" not in captured["environment"]
    assert Path(captured["cwd"]).name.startswith("lecturefoundry-codex-")
    assert result.text == "<html>codex</html>"


def test_codex_rejects_profiles_that_can_restore_customizations() -> None:
    with pytest.raises(ValueError, match="profiles are disabled"):
        CodexCLIBackend(profile="lecture")


def test_codex_is_disabled_for_untrusted_transcripts_by_default() -> None:
    backend = CodexCLIBackend(executable_finder=lambda command: "/usr/bin/codex")

    status = backend.check()

    assert not status.available
    assert "allow_agentic_file_reads" in status.detail
    with pytest.raises(AIBackendError, match="tool-free OpenAI API backend"):
        backend.generate(GenerationRequest(prompt="Untrusted transcript"))


def test_claude_uses_non_interactive_plan_mode(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setenv("COURSERA_CAUTH", "must-not-leak")

    def runner(arguments, **kwargs):
        captured["arguments"] = arguments
        captured["environment"] = kwargs["env"]
        captured["cwd"] = kwargs["cwd"]
        return subprocess.CompletedProcess(
            arguments, 0, stdout="<html>claude</html>\n", stderr=""
        )

    backend = ClaudeCLIBackend(model="sonnet", runner=runner)
    result = backend.generate(
        GenerationRequest(prompt="Build it", response_schema=lesson_content_schema())
    )

    assert "--print" in captured["arguments"]
    assert ["--permission-mode", "plan"] == captured["arguments"][
        captured["arguments"].index("--permission-mode") :
        captured["arguments"].index("--permission-mode") + 2
    ]
    assert "--safe-mode" in captured["arguments"]
    assert "--restricted" in captured["arguments"]
    assert "--strict-mcp-config" in captured["arguments"]
    assert "--json-schema" in captured["arguments"]
    sent_schema = captured["arguments"][captured["arguments"].index("--json-schema") + 1]
    assert "minLength" not in sent_schema
    assert "COURSERA_CAUTH" not in captured["environment"]
    assert Path(captured["cwd"]).name.startswith("lecturefoundry-claude-")
    assert result.text == "<html>claude</html>"


def test_command_backend_surfaces_nonzero_exit() -> None:
    def runner(arguments, **kwargs):
        return subprocess.CompletedProcess(arguments, 2, stdout="", stderr="bad auth")

    backend = ClaudeCLIBackend(runner=runner)

    with pytest.raises(AIBackendError, match="bad auth"):
        backend.generate(GenerationRequest(prompt="Build it"))


def test_http_retry_policy_never_replays_generation_posts() -> None:
    retries = retrying_session().get_adapter("https://").max_retries

    assert retries.allowed_methods == frozenset({"GET"})
    assert retries.read == 0


def test_schema_projection_preserves_property_names_that_match_keywords() -> None:
    schema = {
        "type": "object",
        "properties": {
            "minLength": {"type": "string", "minLength": 1},
        },
        "required": ["minLength"],
        "additionalProperties": False,
    }

    projected = schema_for_provider(schema, "openai")

    assert "minLength" in projected["properties"]
    assert "minLength" not in projected["properties"]["minLength"]
