"""Platform-neutral data passed between application layers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse


class TranscriptFormat(str, Enum):
    TXT = "txt"
    SRT = "srt"


@dataclass(frozen=True, slots=True)
class FetchRequest:
    """Inputs needed to fetch transcripts from any provider."""

    slug: str
    output_dir: Path
    language: str = "en"
    transcript_format: TranscriptFormat = TranscriptFormat.TXT

    def __post_init__(self) -> None:
        if not self.slug.strip():
            raise ValueError("Course slug cannot be empty")
        if not self.language.strip():
            raise ValueError("Language cannot be empty")


@dataclass(frozen=True, slots=True)
class FetchResult:
    """Provider-independent summary suitable for a CLI or UI."""

    provider: str
    course_slug: str
    output_dir: Path
    downloaded: int
    skipped: int
    failed: int
    total: int
    warnings: tuple[str, ...] = ()
    lecture_keys: tuple[tuple[int, int], ...] | None = None

    @property
    def succeeded(self) -> bool:
        return self.failed == 0 and self.total > 0 and (
            self.downloaded + self.skipped == self.total
        )


@dataclass(frozen=True, slots=True)
class PlaylistFetchRequest:
    """Inputs for importing captions from an ordered online playlist."""

    url: str
    output_dir: Path
    language: str = "en"
    course_slug: str | None = None
    max_videos: int | None = None
    force: bool = False

    def __post_init__(self) -> None:
        parsed = urlparse(self.url)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"} or hostname not in {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "music.youtube.com",
            "youtu.be",
        }:
            raise ValueError("A valid YouTube playlist URL is required")
        if not self.language.strip():
            raise ValueError("Caption language cannot be empty")
        if self.course_slug is not None and not self.course_slug.strip():
            raise ValueError("Course slug cannot be empty")
        if self.max_videos is not None and self.max_videos < 1:
            raise ValueError("Maximum videos must be at least 1")
