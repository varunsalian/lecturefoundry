from pathlib import Path

import pytest

from lecturefoundry.models import (
    FetchRequest,
    FetchResult,
    PlaylistFetchRequest,
    TranscriptFormat,
)


def test_fetch_request_defaults() -> None:
    request = FetchRequest(slug="example-course", output_dir=Path("transcripts"))

    assert request.language == "en"
    assert request.transcript_format is TranscriptFormat.TXT


@pytest.mark.parametrize("field", ["slug", "language"])
def test_fetch_request_rejects_blank_values(field: str) -> None:
    values = {"slug": "example-course", "language": "en"}
    values[field] = "  "

    with pytest.raises(ValueError):
        FetchRequest(output_dir=Path("transcripts"), **values)


def test_fetch_result_treats_all_skipped_as_success() -> None:
    result = FetchResult(
        provider="coursera",
        course_slug="example-course",
        output_dir=Path("transcripts/example-course"),
        downloaded=0,
        skipped=3,
        failed=0,
        total=3,
    )

    assert result.succeeded


def test_playlist_fetch_request_validates_url_and_limit() -> None:
    request = PlaylistFetchRequest(
        url="https://www.youtube.com/playlist?list=example",
        output_dir=Path("transcripts"),
        max_videos=3,
    )

    assert request.language == "en"
    assert request.max_videos == 3

    with pytest.raises(ValueError, match="YouTube playlist URL"):
        PlaylistFetchRequest(
            url="https://example.com/playlist",
            output_dir=Path("transcripts"),
        )
