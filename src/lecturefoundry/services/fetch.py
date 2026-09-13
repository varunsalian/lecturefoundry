"""Transcript-ingestion use case."""

from lecturefoundry.models import FetchRequest, FetchResult
from lecturefoundry.providers.base import TranscriptProvider


def fetch_transcripts(
    provider: TranscriptProvider,
    request: FetchRequest,
) -> FetchResult:
    """Fetch transcripts without coupling the caller to a platform SDK."""

    return provider.fetch(request)
