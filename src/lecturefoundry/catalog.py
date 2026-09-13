"""Ordered course catalogs that connect Coursera metadata to local transcripts."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


CATALOG_FILENAME = "course.json"


def slugify(value: str) -> str:
    """Create a stable, filesystem-safe slug."""

    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "untitled"


def _matching_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", slugify(value))


@dataclass(frozen=True, slots=True)
class LectureRecord:
    number: int
    title: str
    slug: str
    transcript: str
    source_id: str = ""


@dataclass(frozen=True, slots=True)
class ModuleRecord:
    number: int
    title: str
    slug: str
    lectures: tuple[LectureRecord, ...]


@dataclass(frozen=True, slots=True)
class CourseCatalog:
    course_slug: str
    modules: tuple[ModuleRecord, ...]
    version: int = 1
    source_provider: str = ""
    source_id: str = ""
    source_url: str = ""
    title: str = ""

    def find(self, module_number: int, lecture_number: int) -> tuple[ModuleRecord, LectureRecord]:
        for module in self.modules:
            if module.number != module_number:
                continue
            for lecture in module.lectures:
                if lecture.number == lecture_number:
                    return module, lecture
            raise ValueError(
                f"Module {module_number:02d} has no lecture {lecture_number:02d}"
            )
        raise ValueError(f"Course has no module {module_number:02d}")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("source_provider", "source_id", "source_url", "title"):
            if not data[key]:
                del data[key]
        for module in data["modules"]:
            for lecture in module["lectures"]:
                if not lecture["source_id"]:
                    del lecture["source_id"]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CourseCatalog":
        modules = tuple(
            ModuleRecord(
                number=int(module["number"]),
                title=str(module["title"]),
                slug=str(module["slug"]),
                lectures=tuple(
                    LectureRecord(
                        number=int(lecture["number"]),
                        title=str(lecture["title"]),
                        slug=str(lecture["slug"]),
                        transcript=str(lecture["transcript"]),
                        source_id=str(lecture.get("source_id", "")),
                    )
                    for lecture in module.get("lectures", [])
                ),
            )
            for module in data.get("modules", [])
        )
        return cls(
            course_slug=str(data["course_slug"]),
            modules=modules,
            version=int(data.get("version", 1)),
            source_provider=str(data.get("source_provider", "")),
            source_id=str(data.get("source_id", "")),
            source_url=str(data.get("source_url", "")),
            title=str(data.get("title", "")),
        )


def load_catalog(course_dir: Path) -> CourseCatalog:
    path = course_dir / CATALOG_FILENAME
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run 'lecturefoundry index --slug {course_dir.name}' first."
        )
    return CourseCatalog.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_catalog(catalog: CourseCatalog, course_dir: Path) -> Path:
    course_dir.mkdir(parents=True, exist_ok=True)
    path = course_dir / CATALOG_FILENAME
    path.write_text(
        json.dumps(catalog.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def _local_transcripts(course_dir: Path) -> dict[tuple[str, str], Path]:
    matches: dict[tuple[str, str], Path] = {}
    for path in sorted(course_dir.glob("*/*")):
        if path.suffix.lower() not in {".txt", ".srt"}:
            continue
        module_name = re.sub(r"^\d+[_-]", "", path.parent.name)
        lecture_name = re.sub(r"^\d+[_-]", "", path.stem)
        matches[(_matching_key(module_name), _matching_key(lecture_name))] = path
    return matches


def _item_id(element_id: str) -> str:
    return element_id.split("~", 1)[-1]


def catalog_from_coursera_materials(
    course_slug: str,
    materials: dict[str, Any],
    course_dir: Path,
) -> CourseCatalog:
    """Build a catalog in Coursera order and map it to downloaded files."""

    elements = materials.get("elements", [])
    if not elements:
        raise ValueError("Coursera returned no course elements")

    linked = materials.get("linked", {})
    module_lookup = {
        item["id"]: item
        for item in linked.get("onDemandCourseMaterialModules.v1", [])
    }
    lesson_lookup = {
        item["id"]: item
        for item in linked.get("onDemandCourseMaterialLessons.v1", [])
    }
    item_lookup = {
        item["id"]: item
        for item in linked.get("onDemandCourseMaterialItems.v2", [])
    }
    local_files = _local_transcripts(course_dir)
    modules: list[ModuleRecord] = []

    for module_number, module_id in enumerate(elements[0].get("moduleIds", []), 1):
        raw_module = module_lookup.get(module_id)
        if raw_module is None:
            continue
        module_title = str(raw_module.get("name") or f"Module {module_number}")
        module_slug = slugify(str(raw_module.get("slug") or module_title))
        lectures: list[LectureRecord] = []

        for lesson_id in raw_module.get("lessonIds", []):
            lesson = lesson_lookup.get(lesson_id, {})
            for element_id in lesson.get("elementIds", []):
                item = item_lookup.get(_item_id(str(element_id)))
                if item is None:
                    continue
                if item.get("contentSummary", {}).get("typeName") != "lecture":
                    continue
                if item.get("isLocked", False):
                    continue

                title = str(item.get("name") or "Untitled lecture").strip()
                lecture_slug = slugify(str(item.get("slug") or title))
                transcript_path = local_files.get(
                    (_matching_key(module_slug), _matching_key(title))
                )
                if transcript_path is None:
                    transcript_path = local_files.get(
                        (_matching_key(module_title), _matching_key(title))
                    )
                transcript = (
                    str(transcript_path.relative_to(course_dir))
                    if transcript_path is not None
                    else ""
                )
                lectures.append(
                    LectureRecord(
                        number=len(lectures) + 1,
                        title=title,
                        slug=lecture_slug,
                        transcript=transcript,
                    )
                )

        modules.append(
            ModuleRecord(
                number=module_number,
                title=module_title,
                slug=module_slug,
                lectures=tuple(lectures),
            )
        )

    if not modules:
        raise ValueError("Coursera returned no ordered modules")
    return CourseCatalog(course_slug=course_slug, modules=tuple(modules))


def missing_transcripts(catalog: CourseCatalog) -> Iterable[tuple[ModuleRecord, LectureRecord]]:
    for module in catalog.modules:
        for lecture in module.lectures:
            if not lecture.transcript:
                yield module, lecture
