import json
from pathlib import Path

import pytest

from lecturefoundry.catalog import load_catalog
from lecturefoundry.models import PlaylistFetchRequest
from lecturefoundry.providers.youtube import (
    YouTubeProvider,
    YouTubeProviderError,
    caption_to_text,
)


class _Response:
    def __init__(self, payload: str) -> None:
        self._payload = payload.encode()
        self.closed = False

    def read(self) -> bytes:
        return self._payload

    def close(self) -> None:
        self.closed = True


class _FakeYDL:
    instances = []

    def __init__(self, options: dict) -> None:
        self.options = options
        self.opened_urls = []
        self.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        pass

    def extract_info(self, url: str, *, download: bool):
        assert not download
        return {
            "id": "playlist-example",
            "title": "Example Playlist",
            "entries": [
                {
                    "id": "video-two",
                    "title": "Second lesson",
                    "playlist_index": 3,
                    "automatic_captions": {
                        "en-US": [
                            {"ext": "vtt", "url": "https://captions/automatic"}
                        ]
                    },
                },
                {
                    "id": "video-one",
                    "title": "First lesson",
                    "playlist_index": 1,
                    "subtitles": {
                        "en": [
                            {"ext": "json3", "url": "https://captions/manual"}
                        ]
                    },
                    "automatic_captions": {
                        "en": [
                            {"ext": "vtt", "url": "https://captions/not-used"}
                        ]
                    },
                },
                None,
            ],
        }

    def urlopen(self, url: str) -> _Response:
        self.opened_urls.append(url)
        if url.endswith("manual"):
            return _Response(
                json.dumps(
                    {
                        "events": [
                            {"segs": [{"utf8": "First idea. "}]},
                            {"segs": [{"utf8": "Second idea."}]},
                        ]
                    }
                )
            )
        return _Response(
            """WEBVTT

00:00:00.000 --> 00:00:01.000
Automatic captions

00:00:01.000 --> 00:00:02.000
Automatic captions continue
"""
        )


def test_imports_playlist_captions_in_order_and_creates_catalog(
    tmp_path: Path,
) -> None:
    provider = YouTubeProvider(ydl_factory=_FakeYDL)

    result = provider.fetch(
        PlaylistFetchRequest(
            url="https://www.youtube.com/playlist?list=example",
            output_dir=tmp_path,
        )
    )

    assert result.course_slug.startswith("example-playlist-yt-playlist-example-")
    assert result.downloaded == 2
    assert result.failed == 1
    assert result.total == 3
    assert result.lecture_keys == ((1, 1), (1, 3))
    catalog = load_catalog(result.output_dir)
    assert catalog.source_provider == "youtube"
    assert catalog.source_id == "playlist-example"
    assert [lecture.title for lecture in catalog.modules[0].lectures] == [
        "First lesson",
        "Second lesson",
    ]
    assert [lecture.number for lecture in catalog.modules[0].lectures] == [1, 3]
    assert [lecture.source_id for lecture in catalog.modules[0].lectures] == [
        "video-one",
        "video-two",
    ]
    first, second = catalog.modules[0].lectures
    assert (result.output_dir / first.transcript).read_text().strip() == (
        "First idea. Second idea."
    )
    assert (result.output_dir / second.transcript).read_text().strip() == (
        "Automatic captions continue"
    )
    assert _FakeYDL.instances[-1].opened_urls == [
        "https://captions/manual",
        "https://captions/automatic",
    ]
    assert _FakeYDL.instances[-1].options["skip_download"] is True


def test_caption_parser_removes_srt_timing_and_overlap() -> None:
    payload = """1
00:00:00,000 --> 00:00:01,000
Build useful notes

2
00:00:01,000 --> 00:00:02,000
useful notes from captions
"""

    assert caption_to_text(payload, "srt") == "Build useful notes from captions"


def _video(video_id: str, title: str, position: int, caption_url: str) -> dict:
    return {
        "id": video_id,
        "title": title,
        "playlist_index": position,
        "subtitles": {"en": [{"ext": "vtt", "url": caption_url}]},
    }


class _ScenarioYDL:
    def __init__(
        self,
        options: dict,
        *,
        playlist_id: str,
        title: str,
        entries: list,
        failing_urls: set[str],
    ) -> None:
        self.options = options
        self.playlist_id = playlist_id
        self.title = title
        self.entries = entries
        self.failing_urls = failing_urls
        self.opened_urls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        pass

    def extract_info(self, url: str, *, download: bool):
        return {
            "id": self.playlist_id,
            "title": self.title,
            "entries": self.entries,
        }

    def urlopen(self, url: str) -> _Response:
        self.opened_urls.append(url)
        if url in self.failing_urls:
            raise OSError("temporary caption failure")
        return _Response(
            "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nCaption text"
        )


def _scenario_factory(
    *,
    playlist_id: str,
    title: str = "Shared title",
    entries: list,
    failing_urls: set[str] | None = None,
):
    instances = []

    def factory(options: dict):
        instance = _ScenarioYDL(
            options,
            playlist_id=playlist_id,
            title=title,
            entries=entries,
            failing_urls=failing_urls or set(),
        )
        instances.append(instance)
        return instance

    factory.instances = instances
    return factory


def test_same_title_playlists_get_different_default_folders(tmp_path: Path) -> None:
    entry = _video("video", "Lesson", 1, "https://captions/one")
    first = YouTubeProvider(
        ydl_factory=_scenario_factory(playlist_id="playlist-A", entries=[entry])
    ).fetch(
        PlaylistFetchRequest(
            url="https://www.youtube.com/playlist?list=playlist-A",
            output_dir=tmp_path,
        )
    )
    second = YouTubeProvider(
        ydl_factory=_scenario_factory(playlist_id="playlist-B", entries=[entry])
    ).fetch(
        PlaylistFetchRequest(
            url="https://www.youtube.com/playlist?list=playlist-B",
            output_dir=tmp_path,
        )
    )

    assert first.course_slug != second.course_slug
    assert first.output_dir.is_dir()
    assert second.output_dir.is_dir()


def test_explicit_slug_refuses_a_different_playlist(tmp_path: Path) -> None:
    entry = _video("video", "Lesson", 1, "https://captions/one")
    YouTubeProvider(
        ydl_factory=_scenario_factory(playlist_id="playlist-A", entries=[entry])
    ).fetch(
        PlaylistFetchRequest(
            url="https://www.youtube.com/playlist?list=playlist-A",
            output_dir=tmp_path,
            course_slug="shared",
        )
    )

    with pytest.raises(YouTubeProviderError, match="choose a different --slug"):
        YouTubeProvider(
            ydl_factory=_scenario_factory(playlist_id="playlist-B", entries=[entry])
        ).fetch(
            PlaylistFetchRequest(
                url="https://www.youtube.com/playlist?list=playlist-B",
                output_dir=tmp_path,
                course_slug="shared",
            )
        )


def test_rerun_keeps_identity_across_title_and_order_changes(tmp_path: Path) -> None:
    first_factory = _scenario_factory(
        playlist_id="playlist",
        entries=[
            _video("one", "First", 1, "https://captions/one"),
            _video("two", "Second", 2, "https://captions/two"),
        ],
    )
    request = PlaylistFetchRequest(
        url="https://www.youtube.com/playlist?list=playlist",
        output_dir=tmp_path,
    )
    first = YouTubeProvider(ydl_factory=first_factory).fetch(request)
    original = load_catalog(first.output_dir)
    original_by_id = {
        lecture.source_id: lecture for lecture in original.modules[0].lectures
    }

    second_factory = _scenario_factory(
        playlist_id="playlist",
        title="Renamed playlist",
        entries=[
            _video("two", "Second renamed", 1, "https://captions/two"),
            _video("one", "First", 2, "https://captions/one"),
        ],
    )
    second = YouTubeProvider(ydl_factory=second_factory).fetch(request)
    assert second.output_dir == first.output_dir
    refreshed = load_catalog(second.output_dir)
    refreshed_by_id = {
        lecture.source_id: lecture for lecture in refreshed.modules[0].lectures
    }

    assert second.downloaded == 0
    assert second.skipped == 2
    assert second_factory.instances[0].opened_urls == []
    assert [lecture.source_id for lecture in refreshed.modules[0].lectures] == [
        "two",
        "one",
    ]
    assert refreshed_by_id["two"].title == "Second renamed"
    for source_id in ("one", "two"):
        assert refreshed_by_id[source_id].number == original_by_id[source_id].number
        assert refreshed_by_id[source_id].slug == original_by_id[source_id].slug
        assert refreshed_by_id[source_id].transcript == original_by_id[source_id].transcript


def test_partial_force_refresh_preserves_previous_lectures(tmp_path: Path) -> None:
    initial_factory = _scenario_factory(
        playlist_id="playlist",
        entries=[
            _video("one", "First", 1, "https://captions/one"),
            _video("two", "Second", 2, "https://captions/two"),
        ],
    )
    request = PlaylistFetchRequest(
        url="https://www.youtube.com/playlist?list=playlist",
        output_dir=tmp_path,
    )
    initial = YouTubeProvider(ydl_factory=initial_factory).fetch(request)

    refresh_factory = _scenario_factory(
        playlist_id="playlist",
        entries=[
            _video("one", "First", 1, "https://captions/one"),
            _video("two", "Second", 2, "https://captions/two"),
        ],
        failing_urls={"https://captions/two"},
    )
    refreshed = YouTubeProvider(ydl_factory=refresh_factory).fetch(
        PlaylistFetchRequest(
            url=request.url,
            output_dir=tmp_path,
            force=True,
        )
    )

    catalog = load_catalog(initial.output_dir)
    assert refreshed.failed == 1
    assert [lecture.source_id for lecture in catalog.modules[0].lectures] == [
        "one",
        "two",
    ]
    assert all(
        (initial.output_dir / lecture.transcript).is_file()
        for lecture in catalog.modules[0].lectures
    )


def test_limited_rerun_does_not_truncate_existing_catalog(tmp_path: Path) -> None:
    entries = [
        _video("one", "First", 1, "https://captions/one"),
        _video("two", "Second", 2, "https://captions/two"),
    ]
    factory = _scenario_factory(playlist_id="playlist", entries=entries)
    request = PlaylistFetchRequest(
        url="https://www.youtube.com/playlist?list=playlist",
        output_dir=tmp_path,
    )
    initial = YouTubeProvider(ydl_factory=factory).fetch(request)
    limited = YouTubeProvider(ydl_factory=factory).fetch(
        PlaylistFetchRequest(
            url=request.url,
            output_dir=tmp_path,
            max_videos=1,
        )
    )

    catalog = load_catalog(initial.output_dir)
    assert [lecture.source_id for lecture in catalog.modules[0].lectures] == [
        "one",
        "two",
    ]
    assert any("Preserved 1" in warning for warning in limited.warnings)
    assert limited.lecture_keys == ((1, 1),)
