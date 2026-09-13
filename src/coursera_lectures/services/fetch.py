"""Transcript-ingestion use case."""

from coursera_lectures.models import FetchRequest, FetchResult
from coursera_lectures.providers.base import TranscriptProvider


def fetch_transcripts(
    provider: TranscriptProvider,
    request: FetchRequest,
) -> FetchResult:
    """Fetch transcripts without coupling the caller to a platform SDK."""

    return provider.fetch(request)
