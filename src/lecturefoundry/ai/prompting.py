"""Shared prompt construction for command-backed agents."""

from lecturefoundry.ai.base import GenerationRequest


def combine_prompt(request: GenerationRequest) -> str:
    if not request.system_prompt:
        return request.prompt
    return (
        "System instructions:\n"
        f"{request.system_prompt.strip()}\n\n"
        "Task:\n"
        f"{request.prompt.strip()}\n"
    )
