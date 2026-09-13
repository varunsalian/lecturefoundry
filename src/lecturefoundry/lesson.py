"""Validated structured lesson content returned by AI backends."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any


LESSON_CONTENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "subtitle": {"type": "string", "minLength": 1},
        "summary": {"type": "string", "minLength": 1},
        "key_idea": {"type": "string", "minLength": 1},
        "sections": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string", "minLength": 1},
                    "body": {"type": "string", "minLength": 1},
                    "bullets": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                    },
                },
                "required": ["heading", "body", "bullets"],
                "additionalProperties": False,
            },
        },
        "examples": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "minLength": 1},
                    "explanation": {"type": "string", "minLength": 1},
                },
                "required": ["title", "explanation"],
                "additionalProperties": False,
            },
        },
        "review_questions": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
        "action_prompt": {"type": "string", "minLength": 1},
    },
    "required": [
        "title",
        "subtitle",
        "summary",
        "key_idea",
        "sections",
        "examples",
        "review_questions",
        "action_prompt",
    ],
    "additionalProperties": False,
}


def lesson_content_schema(
    *,
    min_sections: int = 1,
    max_sections: int | None = None,
    min_examples: int = 1,
    max_examples: int | None = None,
    min_questions: int = 1,
    max_questions: int | None = None,
) -> dict[str, Any]:
    """Return an independent schema with pattern-specific collection limits."""

    schema = deepcopy(LESSON_CONTENT_SCHEMA)
    limits = (
        ("sections", min_sections, max_sections),
        ("examples", min_examples, max_examples),
        ("review_questions", min_questions, max_questions),
    )
    for key, minimum, maximum in limits:
        collection = schema["properties"][key]
        collection["minItems"] = minimum
        if maximum is not None:
            collection["maxItems"] = maximum
    return schema


@dataclass(frozen=True, slots=True)
class LessonSection:
    heading: str
    body: str
    bullets: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LessonExample:
    title: str
    explanation: str


@dataclass(frozen=True, slots=True)
class LessonContent:
    title: str
    subtitle: str
    summary: str
    key_idea: str
    sections: tuple[LessonSection, ...]
    examples: tuple[LessonExample, ...]
    review_questions: tuple[str, ...]
    action_prompt: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"AI response field '{key}' must be a non-empty string")
    return value.strip()


def _require_exact_keys(data: dict[str, Any], expected: set[str], context: str) -> None:
    missing = expected - data.keys()
    extra = data.keys() - expected
    if missing:
        raise ValueError(f"AI response {context} is missing: {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"AI response {context} has unexpected keys: {', '.join(sorted(extra))}")


def _text_list(value: Any, key: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"AI response field '{key}' must be a list")
    texts = []
    for index, item in enumerate(value, 1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"AI response field '{key}' item {index} must be a non-empty string"
            )
        texts.append(item.strip())
    return tuple(texts)


def parse_lesson_content(response: str) -> LessonContent:
    """Validate a model response containing exactly one lesson JSON object."""

    try:
        data = json.loads(response.strip())
    except json.JSONDecodeError as error:
        raise ValueError(f"AI response was not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("AI response must be a JSON object")
    _require_exact_keys(data, set(LESSON_CONTENT_SCHEMA["required"]), "object")

    raw_sections = data.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise ValueError("AI response field 'sections' must be a non-empty list")
    sections = []
    for index, item in enumerate(raw_sections, 1):
        if not isinstance(item, dict):
            raise ValueError(f"AI response section {index} must be an object")
        _require_exact_keys(item, {"heading", "body", "bullets"}, f"section {index}")
        sections.append(
            LessonSection(
                heading=_required_text(item, "heading"),
                body=_required_text(item, "body"),
                bullets=_text_list(item.get("bullets", []), "bullets"),
            )
        )

    raw_examples = data.get("examples")
    if not isinstance(raw_examples, list):
        raise ValueError("AI response field 'examples' must be a list")
    examples = []
    for index, item in enumerate(raw_examples, 1):
        if not isinstance(item, dict):
            raise ValueError(f"AI response example {index} must be an object")
        _require_exact_keys(item, {"title", "explanation"}, f"example {index}")
        examples.append(
            LessonExample(
                title=_required_text(item, "title"),
                explanation=_required_text(item, "explanation"),
            )
        )

    review_questions = _text_list(data.get("review_questions"), "review_questions")
    if not review_questions:
        raise ValueError("AI response field 'review_questions' cannot be empty")
    if not examples:
        raise ValueError("AI response field 'examples' cannot be empty")

    return LessonContent(
        title=_required_text(data, "title"),
        subtitle=_required_text(data, "subtitle"),
        summary=_required_text(data, "summary"),
        key_idea=_required_text(data, "key_idea"),
        sections=tuple(sections),
        examples=tuple(examples),
        review_questions=review_questions,
        action_prompt=_required_text(data, "action_prompt"),
    )
