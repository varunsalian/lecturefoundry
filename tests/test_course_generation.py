from pathlib import Path

from lecturefoundry.ai import AIBackendError
from lecturefoundry.catalog import (
    CourseCatalog,
    LectureRecord,
    ModuleRecord,
    save_catalog,
)
from lecturefoundry.services import CourseNotesRequest, generate_course_notes


def test_generates_each_requested_pattern_and_skips_existing(tmp_path: Path) -> None:
    transcripts = tmp_path / "transcripts"
    course_dir = transcripts / "course"
    save_catalog(
        CourseCatalog(
            course_slug="course",
            modules=(
                ModuleRecord(
                    number=1,
                    title="Videos",
                    slug="videos",
                    lectures=(
                        LectureRecord(
                            number=1,
                            title="Lesson",
                            slug="lesson",
                            transcript="01-videos/01-lesson.txt",
                        ),
                    ),
                ),
            ),
        ),
        course_dir,
    )
    generated = []

    def generator(backend, request):
        generated.append(request)
        if request.pattern == "deep-dive":
            raise FileExistsError("already generated")
        return object()

    result = generate_course_notes(
        object(),
        CourseNotesRequest(
            course_slug="course",
            patterns=("revision", "deep-dive"),
            transcripts_dir=transcripts,
            output_dir=tmp_path / "site",
        ),
        generator=generator,
    )

    assert [request.pattern for request in generated] == ["revision", "deep-dive"]
    assert result.generated == 1
    assert result.existing == 1
    assert result.succeeded


def test_stops_batch_after_backend_failure(tmp_path: Path) -> None:
    transcripts = tmp_path / "transcripts"
    course_dir = transcripts / "course"
    save_catalog(
        CourseCatalog(
            course_slug="course",
            modules=(
                ModuleRecord(
                    number=1,
                    title="Videos",
                    slug="videos",
                    lectures=tuple(
                        LectureRecord(
                            number=number,
                            title=f"Lesson {number}",
                            slug=f"lesson-{number}",
                            transcript=f"01-videos/{number:02d}-lesson.txt",
                        )
                        for number in (1, 2)
                    ),
                ),
            ),
        ),
        course_dir,
    )
    attempts = []

    def generator(backend, request):
        attempts.append(request)
        raise AIBackendError("invalid API key")

    result = generate_course_notes(
        object(),
        CourseNotesRequest(
            course_slug="course",
            patterns=("revision", "deep-dive"),
            transcripts_dir=transcripts,
            output_dir=tmp_path / "site",
        ),
        generator=generator,
    )

    assert len(attempts) == 1
    assert len(result.failures) == 1
    assert result.failures[0].error == "invalid API key"


def test_generates_only_explicitly_selected_lectures(tmp_path: Path) -> None:
    transcripts = tmp_path / "transcripts"
    course_dir = transcripts / "course"
    save_catalog(
        CourseCatalog(
            course_slug="course",
            modules=(
                ModuleRecord(
                    number=1,
                    title="Videos",
                    slug="videos",
                    lectures=tuple(
                        LectureRecord(
                            number=number,
                            title=f"Lesson {number}",
                            slug=f"lesson-{number}",
                            transcript=f"01-videos/{number:02d}-lesson.txt",
                        )
                        for number in (1, 2, 3)
                    ),
                ),
            ),
        ),
        course_dir,
    )
    generated = []

    def generator(backend, request):
        generated.append(request)
        return object()

    result = generate_course_notes(
        object(),
        CourseNotesRequest(
            course_slug="course",
            patterns=("revision",),
            transcripts_dir=transcripts,
            output_dir=tmp_path / "site",
            lecture_keys=((1, 2),),
        ),
        generator=generator,
    )

    assert result.generated == 1
    assert [(item.module_number, item.lecture_number) for item in generated] == [
        (1, 2)
    ]
