"""Generate a structured lesson and render it into the numbered site tree."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from lecturefoundry.ai import AIBackend, GenerationRequest
from lecturefoundry.catalog import load_catalog
from lecturefoundry.lesson import lesson_content_schema, parse_lesson_content
from lecturefoundry.patterns import build_lesson_prompt, get_pattern
from lecturefoundry.rendering import render_lesson


@dataclass(frozen=True, slots=True)
class BuildRequest:
    course_slug: str
    module_number: int
    lecture_number: int
    pattern: str
    transcripts_dir: Path = Path("transcripts")
    output_dir: Path = Path("site")
    system_prompt: str = ""
    temperature: float | None = None
    force: bool = False


@dataclass(frozen=True, slots=True)
class BuildResult:
    output_dir: Path
    html_path: Path
    lesson_path: Path
    generation_path: Path
    provider: str
    model: str | None


def _safe_transcript_path(course_dir: Path, relative_path: str) -> Path:
    if not relative_path:
        raise FileNotFoundError(
            "This lecture has no downloaded transcript in the course catalog"
        )
    course_root = course_dir.resolve()
    transcript_path = (course_dir / relative_path).resolve()
    if transcript_path != course_root and course_root not in transcript_path.parents:
        raise ValueError("Catalog transcript path escapes the course directory")
    if not transcript_path.is_file():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")
    return transcript_path


def _json_text(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n"


def _install_directory(staged: Path, destination: Path) -> None:
    """Atomically install a generated directory and restore it if swapping fails."""

    backup = destination.parent / f".{destination.name}.backup-{uuid4().hex}"
    moved_existing = False
    try:
        if destination.exists():
            os.replace(destination, backup)
            moved_existing = True
        os.replace(staged, destination)
    except BaseException:
        if moved_existing and backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)


def generate_lecture(backend: AIBackend, request: BuildRequest) -> BuildResult:
    """Run the selected backend once, validate its JSON, and render safe HTML."""

    pattern = get_pattern(request.pattern)

    course_dir = request.transcripts_dir / request.course_slug
    catalog = load_catalog(course_dir)
    module, lecture = catalog.find(request.module_number, request.lecture_number)
    transcript_path = _safe_transcript_path(course_dir, lecture.transcript)
    transcript = transcript_path.read_text(encoding="utf-8")
    transcript_hash = hashlib.sha256(transcript.encode("utf-8")).hexdigest()

    module_dir = f"{module.number:02d}-{module.slug}"
    lecture_dir = f"{lecture.number:02d}-{lecture.slug}"
    lecture_root = request.output_dir / request.course_slug / module_dir / lecture_dir
    destination = lecture_root / pattern.key
    if destination.exists() and any(destination.iterdir()) and not request.force:
        raise FileExistsError(
            f"Output already exists: {destination}. Pass --force to replace generated files."
        )
    lecture_root.parent.mkdir(parents=True, exist_ok=True)

    prompt = build_lesson_prompt(
        pattern,
        course_slug=request.course_slug,
        module_number=module.number,
        module_title=module.title,
        lecture_number=lecture.number,
        lecture_title=lecture.title,
        transcript=transcript,
    )
    generated = backend.generate(
        GenerationRequest(
            prompt=prompt,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            response_schema=lesson_content_schema(
                min_sections=pattern.min_sections,
                max_sections=pattern.max_sections,
                min_examples=pattern.min_examples,
                max_examples=pattern.max_examples,
                min_questions=pattern.min_questions,
                max_questions=pattern.max_questions,
            ),
            schema_name="lecture_lesson",
        )
    )
    content = parse_lesson_content(generated.text)
    pattern.validate_counts(content)
    html = render_lesson(content, pattern, module, lecture)

    staging = Path(
        tempfile.mkdtemp(prefix=f".{lecture_dir}.staging-", dir=lecture_root.parent)
    )
    staged_destination = staging / pattern.key
    html_path = staged_destination / "index.html"
    lesson_path = staged_destination / "lesson.json"
    generation_path = staged_destination / "generation.json"
    source_path = staging / "source.json"
    lesson_data = {
        "course_slug": request.course_slug,
        "module": {
            "number": module.number,
            "title": module.title,
            "slug": module.slug,
        },
        "lecture": {
            "number": lecture.number,
            "title": lecture.title,
            "slug": lecture.slug,
        },
        "pattern": {
            "key": pattern.key,
            "name": pattern.name,
            "version": pattern.version,
        },
        "content": content.to_dict(),
    }
    generation_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": generated.provider,
        "model": generated.model,
        "pattern": pattern.key,
        "pattern_version": pattern.version,
        "transcript_sha256": transcript_hash,
        "backend_metadata": generated.metadata,
    }

    try:
        if lecture_root.exists():
            shutil.copytree(lecture_root, staging, dirs_exist_ok=True)
        staged_destination.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")
        lesson_path.write_text(_json_text(lesson_data), encoding="utf-8")
        generation_path.write_text(_json_text(generation_data), encoding="utf-8")
        source_path.write_text(
            _json_text(
                {
                    "course_slug": request.course_slug,
                    "module": {
                        "number": module.number,
                        "title": module.title,
                        "slug": module.slug,
                    },
                    "lecture": asdict(lecture),
                    "transcript_sha256": transcript_hash,
                }
            ),
            encoding="utf-8",
        )
        _install_directory(staging, lecture_root)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    html_path = destination / "index.html"
    lesson_path = destination / "lesson.json"
    generation_path = destination / "generation.json"
    return BuildResult(
        output_dir=destination,
        html_path=html_path,
        lesson_path=lesson_path,
        generation_path=generation_path,
        provider=generated.provider,
        model=generated.model,
    )
