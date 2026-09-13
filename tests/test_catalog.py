import json
from pathlib import Path

from lecturefoundry.catalog import (
    catalog_from_coursera_materials,
    load_catalog,
    save_catalog,
    slugify,
)
from lecturefoundry.models import FetchRequest
from lecturefoundry.providers.coursera import CourseraProvider


def _materials() -> dict:
    return {
        "elements": [{"moduleIds": ["module-a"]}],
        "linked": {
            "onDemandCourseMaterialModules.v1": [
                {
                    "id": "module-a",
                    "name": "Introduction",
                    "slug": "introduction",
                    "lessonIds": ["lesson-a"],
                }
            ],
            "onDemandCourseMaterialLessons.v1": [
                {
                    "id": "lesson-a",
                    "elementIds": ["item~lecture-a", "item~reading-a"],
                }
            ],
            "onDemandCourseMaterialItems.v2": [
                {
                    "id": "lecture-a",
                    "name": "What is the G.I. Joe Fallacy?",
                    "slug": "what-is-the-gi-joe-fallacy",
                    "isLocked": False,
                    "contentSummary": {"typeName": "lecture"},
                },
                {
                    "id": "reading-a",
                    "name": "Read me",
                    "isLocked": False,
                    "contentSummary": {"typeName": "supplement"},
                },
            ],
        },
    }


def test_catalog_preserves_course_order_and_matches_legacy_file(tmp_path: Path) -> None:
    transcript = tmp_path / "introduction" / "What is the G.I. Joe Fallacy.txt"
    transcript.parent.mkdir()
    transcript.write_text("Knowing is not enough.", encoding="utf-8")

    catalog = catalog_from_coursera_materials("well-being", _materials(), tmp_path)

    module, lecture = catalog.find(1, 1)
    assert module.slug == "introduction"
    assert lecture.title == "What is the G.I. Joe Fallacy?"
    assert lecture.transcript == "introduction/What is the G.I. Joe Fallacy.txt"


def test_catalog_round_trip(tmp_path: Path) -> None:
    transcript = tmp_path / "introduction" / "What is the G.I. Joe Fallacy.txt"
    transcript.parent.mkdir()
    transcript.write_text("Text", encoding="utf-8")
    original = catalog_from_coursera_materials("well-being", _materials(), tmp_path)

    path = save_catalog(original, tmp_path)
    loaded = load_catalog(tmp_path)

    serialized = json.loads(path.read_text())
    assert serialized["version"] == 1
    assert "source_provider" not in serialized
    assert "source_id" not in serialized["modules"][0]["lectures"][0]
    assert loaded == original
    assert slugify("G.I. Joe & Happiness!") == "g-i-joe-happiness"


def test_fetch_automatically_saves_ordered_catalog(tmp_path: Path) -> None:
    materials = _materials()

    class FakeAPI:
        def __init__(self, cookie: str) -> None:
            self.cookie = cookie

        def get_course_materials(self, slug: str) -> dict:
            return materials

    class FakeDownloader:
        def __init__(self, api, output_dir: Path, **kwargs) -> None:
            self.api = api
            self.output_dir = output_dir

        def fetch_all_transcripts(self, slug: str) -> dict[str, int]:
            self.api.get_course_materials(slug)
            path = self.output_dir / slug / "introduction" / "What is the G.I. Joe Fallacy.txt"
            path.parent.mkdir(parents=True)
            path.write_text("Transcript", encoding="utf-8")
            return {"success": 1, "skipped": 0, "failed": 0, "total": 1}

    provider = CourseraProvider(
        "secret",
        api_factory=FakeAPI,
        downloader_factory=FakeDownloader,
    )
    provider.fetch(FetchRequest(slug="well-being", output_dir=tmp_path))

    catalog = load_catalog(tmp_path / "well-being")
    assert catalog.find(1, 1)[1].transcript.endswith("G.I. Joe Fallacy.txt")
