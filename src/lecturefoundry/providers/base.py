"""Interfaces implemented by transcript sources."""

from typing import Protocol

from lecturefoundry.models import FetchRequest, FetchResult


class TranscriptProvider(Protocol):
    """A source capable of fetching a course's transcripts."""

    name: str

    def fetch(self, request: FetchRequest) -> FetchResult:
        """Fetch transcripts and return a platform-neutral summary."""
        ...
