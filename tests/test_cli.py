from pathlib import Path

import lecturefoundry.cli as cli
from lecturefoundry.ai import BackendStatus
from lecturefoundry.cli import _uses_remote_service
from lecturefoundry.catalog import CourseCatalog, LectureRecord, ModuleRecord, save_catalog
from lecturefoundry.config import AISettings
from lecturefoundry.models import FetchResult
from lecturefoundry.services import CourseNotesResult


def test_remote_notice_includes_agentic_cli_backends() -> None:
    assert _uses_remote_service("codex", {})
    assert _uses_remote_service("claude", {})


def test_local_ollama_does_not_get_remote_notice() -> None:
    assert not _uses_remote_service(
        "ollama", {"base_url": "http://localhost:11434"}
    )


def test_unverified_backend_check_is_not_reported_as_success(
    monkeypatch, capsys
) -> None:
    class Backend:
        def check(self) -> BackendStatus:
            return BackendStatus(
                "codex", True, "credential present but not verified", verified=False
            )

    monkeypatch.setattr(
        cli,
        "load_ai_settings",
        lambda *args, **kwargs: AISettings(provider="codex"),
    )
    monkeypatch.setattr(cli, "create_ai_backend", lambda settings: Backend())

    exit_code = cli.main(["ai", "check", "--config", str(Path("missing.toml"))])

    assert exit_code == 2
    assert capsys.readouterr().out.startswith("[CONFIGURED] codex:")


def test_youtube_command_imports_and_generates_default_revision(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    transcripts = tmp_path / "transcripts"
    output = tmp_path / "site"
    generated = []

    class Provider:
        def fetch(self, request):
            course_dir = request.output_dir / "example-playlist"
            transcript = course_dir / "01-videos" / "01-lesson.txt"
            transcript.parent.mkdir(parents=True)
            transcript.write_text("Caption text")
            save_catalog(
                CourseCatalog(
                    course_slug="example-playlist",
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
            return FetchResult(
                provider="youtube",
                course_slug="example-playlist",
                output_dir=course_dir,
                downloaded=1,
                skipped=0,
                failed=0,
                total=1,
                lecture_keys=((1, 1),),
            )

    monkeypatch.setattr(cli, "YouTubeProvider", lambda: Provider())
    monkeypatch.setattr(
        cli,
        "load_ai_settings",
        lambda *args, **kwargs: AISettings(
            provider="ollama",
            options={"base_url": "http://localhost:11434"},
        ),
    )

    class Backend:
        def check(self):
            return BackendStatus("ollama", True, "ready")

    monkeypatch.setattr(cli, "create_ai_backend", lambda settings: Backend())

    def generate_notes(backend, request, *, on_start):
        generated.append(request)
        return CourseNotesResult(
            output_dir=request.output_dir / request.course_slug,
            generated=1,
            existing=0,
            failures=(),
        )

    monkeypatch.setattr(cli, "generate_course_notes", generate_notes)

    exit_code = cli.main(
        [
            "youtube",
            "https://www.youtube.com/playlist?list=example",
            "--transcripts",
            str(transcripts),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert len(generated) == 1
    assert generated[0].patterns == ("revision",)
    assert generated[0].course_slug == "example-playlist"
    assert generated[0].lecture_keys == ((1, 1),)
    assert "Generated 1 note sets" in capsys.readouterr().out


def test_youtube_command_checks_backend_before_import(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    imported = []

    class Provider:
        def fetch(self, request):
            imported.append(request)

    class Backend:
        def check(self):
            return BackendStatus("ollama", False, "model is missing")

    monkeypatch.setattr(cli, "YouTubeProvider", lambda: Provider())
    monkeypatch.setattr(
        cli,
        "load_ai_settings",
        lambda *args, **kwargs: AISettings(
            provider="ollama",
            options={"base_url": "http://localhost:11434"},
        ),
    )
    monkeypatch.setattr(cli, "create_ai_backend", lambda settings: Backend())

    exit_code = cli.main(
        [
            "youtube",
            "https://www.youtube.com/playlist?list=example",
            "--transcripts",
            str(tmp_path / "transcripts"),
        ]
    )

    assert exit_code == 1
    assert imported == []
    assert "backend is unavailable" in capsys.readouterr().err
