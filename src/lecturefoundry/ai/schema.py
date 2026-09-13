"""Project canonical schemas into provider-supported JSON Schema subsets."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any


_CONSTRAINT_KEYWORDS = {
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "minimum",
    "maximum",
    "multipleOf",
    "minItems",
    "maxItems",
}

_REMOVED_KEYWORDS = {
    # Use the conservative subset that also works for fine-tuned and partially
    # compatible models. The complete constraints are still checked locally.
    "openai": _CONSTRAINT_KEYWORDS,
    # Codex CLI targets current base models whose Structured Outputs support
    # array cardinality constraints. Retaining these prevents constrained
    # decoding from producing empty or incorrectly sized pattern collections.
    "codex": _CONSTRAINT_KEYWORDS - {"minItems", "maxItems"},
    "openai-compatible": _CONSTRAINT_KEYWORDS,
    "anthropic": {
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "multipleOf",
        "maxItems",
    },
    "claude": {
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "multipleOf",
        "maxItems",
    },
    "gemini": {"minLength", "maxLength", "pattern", "multipleOf"},
}


def schema_for_provider(schema: dict[str, Any], provider: str) -> dict[str, Any]:
    """Return an independent schema containing only supported provider keywords.

    The complete schema remains available to local validation. Providers receive a
    compatible structural schema, while prompt instructions describe constraints
    that their constrained decoders cannot express.
    """

    removed = _REMOVED_KEYWORDS.get(provider)
    if not removed:
        return deepcopy(schema)

    def project(value: Any) -> Any:
        if isinstance(value, list):
            return [project(item) for item in value]
        if not isinstance(value, dict):
            return value

        result: dict[str, Any] = {}
        for key, item in value.items():
            if key == "properties" and isinstance(item, dict):
                result[key] = {
                    property_name: project(property_schema)
                    for property_name, property_schema in item.items()
                }
                continue
            if key in removed:
                continue
            if provider in {"anthropic", "claude"} and key == "minItems":
                if not isinstance(item, int) or item not in {0, 1}:
                    continue
            result[key] = project(item)
        return result

    return project(schema)


def prompt_with_schema(prompt: str, schema: dict[str, Any] | None) -> str:
    """Include the schema in the prompt when native constrained output is unavailable."""

    if schema is None:
        return prompt
    return (
        f"{prompt.rstrip()}\n\nRequired JSON Schema:\n"
        f"{json.dumps(schema, ensure_ascii=False, separators=(',', ':'))}\n"
    )
