from pathlib import Path

import pytest

from lecturefoundry.models import FetchRequest, TranscriptFormat
from lecturefoundry.providers.coursera import CourseraProvider, normalize_cauth


class FakeDownloader:
    received: dict = {}

    def __init__(self, **kwargs) -> None:
        self.received = kwargs
        FakeDownloader.received = kwargs

    def fetch_all_transcripts(self, slug: str) -> dict[str, int]:
        FakeDownloader.received["slug"] = slug
        return {"success": 3, "skipped": 1, "failed": 0, "total": 4}


def test_normalize_cauth() -> None:
    assert normalize_cauth("secret") == "CAUTH=secret"
    assert normalize_cauth(" CAUTH=secret ") == "CAUTH=secret"


def test_normalize_cauth_rejects_empty_token() -> None:
    with pytest.raises(ValueError):
        normalize_cauth(" ")


def test_provider_maps_upstream_stats_to_core_result(tmp_path: Path) -> None:
    cookies: list[str] = []
    console = object()

    def api_factory(cookie: str, **kwargs) -> object:
        cookies.append(cookie)
        assert kwargs["console"] is console
        return object()

    provider = CourseraProvider(
        "secret",
        api_factory=api_factory,
        downloader_factory=FakeDownloader,
        console=console,
    )
    request = FetchRequest(
        slug="example-course",
        output_dir=tmp_path,
        language="fr",
        transcript_format=TranscriptFormat.SRT,
    )

    result = provider.fetch(request)

    assert cookies == ["CAUTH=secret"]
    assert FakeDownloader.received["language"] == "fr"
    assert FakeDownloader.received["fmt"] == "srt"
    assert FakeDownloader.received["console"] is console
    assert FakeDownloader.received["slug"] == "example-course"
    assert result.downloaded == 3
    assert result.skipped == 1
    assert result.output_dir == tmp_path / "example-course"
    assert result.succeeded
