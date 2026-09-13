import json
from pathlib import Path

import pytest

from lecturefoundry.ai import GenerationResult
from lecturefoundry.build import BuildRequest, generate_lecture
from lecturefoundry.catalog import (
    CourseCatalog,
    LectureRecord,
    ModuleRecord,
    save_catalog,
)
from lecturefoundry.lesson import parse_lesson_content


MODEL_JSON = json.dumps(
    {
        "title": "Knowing <em>isn't</em> enough",
        "subtitle": "Learn why information does not automatically change behavior.",
        "summary": "Knowledge and automatic responses can disagree.",
        "key_idea": "Seeing the trick does not stop the trick.",
        "sections": [
            {
                "heading": "The mistaken shortcut",
                "body": "Awareness is a beginning rather than an outcome.",
                "bullets": ["Notice", "Practice"],
            },
            {
                "heading": "Automatic responses",
                "body": "Fast reactions can remain unchanged after an explanation.",
                "bullets": [],
            },
            {
                "heading": "Practice closes the gap",
                "body": "Repeated action helps turn knowledge into behavior.",
                "bullets": ["Repeat"],
            },
        ],
        "examples": [
            {
                "title": "Visual illusion",
                "explanation": "Equal lines can continue to look different.",
            },
            {
                "title": "Repeated habit",
                "explanation": "Knowing a better response still requires practice.",
            },
        ],
        "review_questions": [
            "What is the central mistake?",
            "Why can automatic responses persist?",
            "What helps close the knowledge-action gap?",
        ],
        "action_prompt": "Attach one useful insight to a repeated action.",
    }
)


class FakeBackend:
    name = "fake"

    def __init__(self) -> None:
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return GenerationResult(MODEL_JSON, provider="fake", model="small")


def _course(tmp_path: Path) -> tuple[Path, Path]:
    transcripts = tmp_path / "transcripts"
    course_dir = transcripts / "well-being"
    source = course_dir / "introduction" / "Lecture One.txt"
    source.parent.mkdir(parents=True)
    source.write_text("The transcript.", encoding="utf-8")
    save_catalog(
        CourseCatalog(
            course_slug="well-being",
            modules=(
                ModuleRecord(
                    number=1,
                    title="Introduction",
                    slug="introduction",
                    lectures=(
                        LectureRecord(
                            number=4,
                            title="Lecture One",
                            slug="lecture-one",
                            transcript="introduction/Lecture One.txt",
                        ),
                    ),
                ),
            ),
        ),
        course_dir,
    )
    return transcripts, tmp_path / "site"


def test_generation_uses_numbered_module_and_lecture_directories(tmp_path: Path) -> None:
    transcripts, output = _course(tmp_path)
    backend = FakeBackend()

    result = generate_lecture(
        backend,
        BuildRequest(
            course_slug="well-being",
            module_number=1,
            lecture_number=4,
            pattern="revision",
            transcripts_dir=transcripts,
            output_dir=output,
        ),
    )

    expected = output / "well-being" / "01-introduction" / "04-lecture-one" / "revision"
    assert result.output_dir == expected
    assert result.html_path.exists()
    assert (expected / "lesson.json").exists()
    assert (expected / "generation.json").exists()
    assert (expected.parent / "source.json").exists()
    html = result.html_path.read_text(encoding="utf-8")
    assert "Module 01 · Lecture 04" in html
    assert "&lt;em&gt;isn&#x27;t&lt;/em&gt;" in html
    assert "Transcript:" in backend.requests[0].prompt
    assert "not general knowledge or material from other lectures" in backend.requests[0].prompt
    assert "never invent a hypothetical" in backend.requests[0].prompt
    assert "does not mean \"global\"" in backend.requests[0].prompt


def test_generation_protects_existing_output(tmp_path: Path) -> None:
    transcripts, output = _course(tmp_path)
    request = BuildRequest(
        course_slug="well-being",
        module_number=1,
        lecture_number=4,
        pattern="revision",
        transcripts_dir=transcripts,
        output_dir=output,
    )
    generate_lecture(FakeBackend(), request)

    with pytest.raises(FileExistsError, match="--force"):
        generate_lecture(FakeBackend(), request)


def test_force_replaces_generated_files_and_preserves_other_files(tmp_path: Path) -> None:
    transcripts, output = _course(tmp_path)
    request = BuildRequest(
        course_slug="well-being",
        module_number=1,
        lecture_number=4,
        pattern="revision",
        transcripts_dir=transcripts,
        output_dir=output,
    )
    first = generate_lecture(FakeBackend(), request)
    custom = first.output_dir / "notes.txt"
    custom.write_text("keep me", encoding="utf-8")

    replaced = generate_lecture(
        FakeBackend(),
        BuildRequest(
            course_slug=request.course_slug,
            module_number=request.module_number,
            lecture_number=request.lecture_number,
            pattern=request.pattern,
            transcripts_dir=request.transcripts_dir,
            output_dir=request.output_dir,
            force=True,
        ),
    )

    assert (replaced.output_dir / "notes.txt").read_text(encoding="utf-8") == "keep me"
    assert not list(replaced.output_dir.parent.parent.glob(".04-lecture-one.staging-*"))


def test_model_json_must_not_be_wrapped_in_a_code_fence() -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_lesson_content(f"```json\n{MODEL_JSON}\n```")


def test_generation_passes_a_strict_lesson_schema(tmp_path: Path) -> None:
    transcripts, output = _course(tmp_path)
    backend = FakeBackend()

    generate_lecture(
        backend,
        BuildRequest(
            course_slug="well-being",
            module_number=1,
            lecture_number=4,
            pattern="revision",
            transcripts_dir=transcripts,
            output_dir=output,
        ),
    )

    schema = backend.requests[0].response_schema
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["sections"]["minItems"] == 3
    assert schema["properties"]["sections"]["maxItems"] == 5
    assert schema["properties"]["examples"]["minItems"] == 2
    assert schema["properties"]["review_questions"]["maxItems"] == 3


def test_generation_rejects_content_that_breaks_pattern_counts(tmp_path: Path) -> None:
    transcripts, output = _course(tmp_path)
    data = json.loads(MODEL_JSON)
    data["sections"] = data["sections"][:1]

    class InvalidBackend(FakeBackend):
        def generate(self, request):
            return GenerationResult(json.dumps(data), provider="fake", model="small")

    with pytest.raises(ValueError, match="3-5 sections"):
        generate_lecture(
            InvalidBackend(),
            BuildRequest(
                course_slug="well-being",
                module_number=1,
                lecture_number=4,
                pattern="revision",
                transcripts_dir=transcripts,
                output_dir=output,
            ),
        )


def test_failed_staging_keeps_previous_lecture_root(tmp_path: Path, monkeypatch) -> None:
    transcripts, output = _course(tmp_path)
    request = BuildRequest(
        course_slug="well-being",
        module_number=1,
        lecture_number=4,
        pattern="revision",
        transcripts_dir=transcripts,
        output_dir=output,
    )
    first = generate_lecture(FakeBackend(), request)
    original_html = first.html_path.read_text(encoding="utf-8")
    original_write_text = Path.write_text

    def failing_write(path: Path, content: str, **kwargs):
        if path.name == "source.json" and ".staging-" in str(path.parent):
            raise OSError("simulated metadata write failure")
        return original_write_text(path, content, **kwargs)

    monkeypatch.setattr(Path, "write_text", failing_write)
    with pytest.raises(OSError, match="metadata write failure"):
        generate_lecture(
            FakeBackend(),
            BuildRequest(
                course_slug=request.course_slug,
                module_number=request.module_number,
                lecture_number=request.lecture_number,
                pattern=request.pattern,
                transcripts_dir=request.transcripts_dir,
                output_dir=request.output_dir,
                force=True,
            ),
        )

    assert first.html_path.read_text(encoding="utf-8") == original_html
    assert not list(first.output_dir.parent.parent.glob(".04-lecture-one.staging-*"))


def test_parser_rejects_non_string_list_items() -> None:
    data = json.loads(MODEL_JSON)
    data["review_questions"] = [{"question": "Wrong type"}]

    with pytest.raises(ValueError, match="non-empty string"):
        parse_lesson_content(json.dumps(data))


def test_parser_rejects_unexpected_keys() -> None:
    data = json.loads(MODEL_JSON)
    data["unexpected"] = True

    with pytest.raises(ValueError, match="unexpected keys"):
        parse_lesson_content(json.dumps(data))
