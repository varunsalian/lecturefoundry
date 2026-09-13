"""Versioned lecture-generation patterns and their content contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PatternSpec:
    key: str
    name: str
    description: str
    instructions: str
    version: str = "1.2"
    min_sections: int = 1
    max_sections: int | None = None
    min_examples: int = 1
    max_examples: int | None = None
    min_questions: int = 1
    max_questions: int | None = None

    def validate_counts(self, content: object) -> None:
        """Enforce the measurable part of this pattern's content contract."""

        checks = (
            (
                "sections",
                len(getattr(content, "sections")),
                self.min_sections,
                self.max_sections,
            ),
            (
                "examples",
                len(getattr(content, "examples")),
                self.min_examples,
                self.max_examples,
            ),
            (
                "review questions",
                len(getattr(content, "review_questions")),
                self.min_questions,
                self.max_questions,
            ),
        )
        for label, actual, minimum, maximum in checks:
            if actual < minimum or (maximum is not None and actual > maximum):
                if minimum == maximum:
                    expected = str(minimum)
                elif maximum is None:
                    expected = f"at least {minimum}"
                else:
                    expected = f"{minimum}-{maximum}"
                raise ValueError(
                    f"{self.name} generation must contain {expected} {label}; received {actual}"
                )


PATTERNS: dict[str, PatternSpec] = {
    "revision": PatternSpec(
        key="revision",
        name="One-page revision",
        description="Compact, print-friendly summary with evidence and retrieval checks.",
        instructions=(
            "Be concise. Use 3-5 short sections, 2-4 concrete examples, "
            "and 3 retrieval questions. The action prompt should turn the core idea into practice."
        ),
        min_sections=3,
        max_sections=5,
        min_examples=2,
        max_examples=4,
        min_questions=3,
        max_questions=3,
    ),
    "deep-dive": PatternSpec(
        key="deep-dive",
        name="Descriptive deep dive",
        description="Detailed narrative explanation grounded entirely in the source.",
        instructions=(
            "Write 4-6 logically ordered sections in an approachable editorial style. "
            "Explain the transcript in detail without adding outside context, terminology, "
            "examples, consequences, or advice."
        ),
        min_sections=4,
        max_sections=6,
    ),
    "active-recall": PatternSpec(
        key="active-recall",
        name="Active recall",
        description="Prediction, retrieval, revealable answers, and practical application.",
        instructions=(
            "Prioritize testing over exposition. Keep section bodies brief, provide 3-6 crisp "
            "examples usable as answer cards, and write 3-5 retrieval questions."
        ),
        min_examples=3,
        max_examples=6,
        min_questions=3,
        max_questions=5,
    ),
    "concept-map": PatternSpec(
        key="concept-map",
        name="Concept map",
        description="Visual argument or causal sequence supported by concrete examples.",
        instructions=(
            "Create exactly 4 short sections that form a logical sequence grounded in the "
            "transcript. Use causal language only when the transcript makes a causal claim. "
            "Each heading must be a compact node label and each body must explain its connection."
        ),
        min_sections=4,
        max_sections=4,
    ),
}


def get_pattern(key: str) -> PatternSpec:
    try:
        return PATTERNS[key]
    except KeyError as error:
        choices = ", ".join(PATTERNS)
        raise ValueError(f"Unknown pattern '{key}'. Choose: {choices}") from error


def build_lesson_prompt(
    pattern: PatternSpec,
    *,
    course_slug: str,
    module_number: int,
    module_title: str,
    lecture_number: int,
    lecture_title: str,
    transcript: str,
) -> str:
    return f"""Create structured content for the lecture pattern below.

Pattern: {pattern.name} ({pattern.key}, version {pattern.version})
Pattern requirements: {pattern.instructions}

Return exactly one valid JSON object matching the response schema supplied by the caller.
Do not use Markdown fences, commentary, or HTML.

Rules:
- Treat the transcript as the source of truth.
- Use only this lecture's transcript, not general knowledge or material from other lectures.
- Every factual sentence must be directly supported by, or be a meaning-preserving paraphrase
  of, a specific part of the transcript.
- Do not introduce named concepts, technical labels, history, attribution, causation, research
  findings, statistics, consequences, recommendations, quotations, or platform policies that
  the transcript does not state.
- Do not broaden the source's scope: for example, "a bigger group" does not mean "global",
  and a warning about one platform does not establish rules for every unofficial platform.
- Preserve uncertainty, correlation-versus-causation, approximate quantities, and ambiguous
  wording instead of silently making them more definite.
- Examples must come from examples or concrete facts in the transcript. If the transcript is
  sparse, reuse or reorganize its facts to satisfy the schema; never invent a hypothetical.
- An action prompt may ask the learner to apply a source idea, but it must not add a factual
  claim or imply that its suggested action appeared in the lecture.
- If a detail is not stated or clearly implied by the transcript, omit it.
- Do not reproduce long transcript passages; summarize and paraphrase.
- Use accessible language and preserve the lecturer's meaning.
- Every review question must be answerable from the generated content.
- Do not repeat the action prompt as a regular section.

Course: {course_slug}
Module {module_number:02d}: {module_title}
Lecture {lecture_number:02d}: {lecture_title}

Transcript:
---
{transcript.strip()}
---
"""
