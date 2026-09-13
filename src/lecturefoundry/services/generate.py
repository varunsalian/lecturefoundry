"""Reusable whole-course note generation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from lecturefoundry.ai import AIBackend, AIBackendError
from lecturefoundry.build import BuildRequest, BuildResult, generate_lecture
from lecturefoundry.catalog import LectureRecord, ModuleRecord, load_catalog
from lecturefoundry.patterns import PATTERNS


@dataclass(frozen=True, slots=True)
class CourseNotesRequest:
    course_slug: str
    patterns: tuple[str, ...]
    transcripts_dir: Path = Path("transcripts")
    output_dir: Path = Path("site")
    system_prompt: str = ""
    temperature: float | None = None
    force: bool = False
    lecture_keys: tuple[tuple[int, int], ...] | None = None

    def __post_init__(self) -> None:
        if not self.course_slug.strip():
            raise ValueError("Course slug cannot be empty")
        if not self.patterns:
            raise ValueError("At least one study pattern is required")
        unknown = set(self.patterns).difference(PATTERNS)
        if unknown:
            raise ValueError(f"Unknown study pattern: {sorted(unknown)[0]}")
        if self.lecture_keys is not None and any(
            module_number < 1 or lecture_number < 1
            for module_number, lecture_number in self.lecture_keys
        ):
            raise ValueError("Lecture module and lecture numbers must be positive")


@dataclass(frozen=True, slots=True)
class NoteGenerationFailure:
    module_number: int
    lecture_number: int
    lecture_title: str
    pattern: str
    error: str


@dataclass(frozen=True, slots=True)
class CourseNotesResult:
    output_dir: Path
    generated: int
    existing: int
    failures: tuple[NoteGenerationFailure, ...]

    @property
    def succeeded(self) -> bool:
        return not self.failures


ProgressCallback = Callable[[ModuleRecord, LectureRecord, str], None]
LectureGenerator = Callable[[AIBackend, BuildRequest], BuildResult]


def generate_course_notes(
    backend: AIBackend,
    request: CourseNotesRequest,
    *,
    on_start: ProgressCallback | None = None,
    generator: LectureGenerator | None = None,
) -> CourseNotesResult:
    """Generate requested patterns for every cataloged lecture."""

    catalog = load_catalog(request.transcripts_dir / request.course_slug)
    generate = generator or generate_lecture
    generated = 0
    existing = 0
    failures = []
    selected = set(request.lecture_keys) if request.lecture_keys is not None else None

    for module in catalog.modules:
        for lecture in module.lectures:
            if selected is not None and (module.number, lecture.number) not in selected:
                continue
            for pattern in request.patterns:
                if on_start is not None:
                    on_start(module, lecture, pattern)
                try:
                    generate(
                        backend,
                        BuildRequest(
                            course_slug=request.course_slug,
                            module_number=module.number,
                            lecture_number=lecture.number,
                            pattern=pattern,
                            transcripts_dir=request.transcripts_dir,
                            output_dir=request.output_dir,
                            system_prompt=request.system_prompt,
                            temperature=request.temperature,
                            force=request.force,
                        ),
                    )
                    generated += 1
                except FileExistsError:
                    existing += 1
                except AIBackendError as error:
                    failures.append(
                        NoteGenerationFailure(
                            module_number=module.number,
                            lecture_number=lecture.number,
                            lecture_title=lecture.title,
                            pattern=pattern,
                            error=str(error),
                        )
                    )
                    return CourseNotesResult(
                        output_dir=request.output_dir / request.course_slug,
                        generated=generated,
                        existing=existing,
                        failures=tuple(failures),
                    )
                except (FileNotFoundError, OSError, ValueError) as error:
                    failures.append(
                        NoteGenerationFailure(
                            module_number=module.number,
                            lecture_number=lecture.number,
                            lecture_title=lecture.title,
                            pattern=pattern,
                            error=str(error),
                        )
                    )

    return CourseNotesResult(
        output_dir=request.output_dir / request.course_slug,
        generated=generated,
        existing=existing,
        failures=tuple(failures),
    )
