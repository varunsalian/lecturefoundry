"""Platform-neutral data passed between application layers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


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

    @property
    def succeeded(self) -> bool:
        return self.failed == 0 and self.total > 0 and (
            self.downloaded + self.skipped == self.total
        )
