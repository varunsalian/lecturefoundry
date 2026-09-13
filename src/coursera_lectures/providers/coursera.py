"""Coursera transcript provider adapter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from coursera_lectures.catalog import catalog_from_coursera_materials, save_catalog
from coursera_lectures.models import FetchRequest, FetchResult


def normalize_cauth(value: str) -> str:
    """Return the cookie header form expected by the upstream client."""

    token = value.strip()
    if not token:
        raise ValueError("Coursera CAUTH token cannot be empty")
    return token if token.startswith("CAUTH=") else f"CAUTH={token}"


class _CatalogingAPI:
    """Remember materials already requested by the upstream downloader."""

    def __init__(self, api: Any) -> None:
        self._api = api
        self.materials: dict[str, Any] | None = None

    def get_course_materials(self, slug: str) -> dict[str, Any]:
        self.materials = self._api.get_course_materials(slug)
        return self.materials

    def __getattr__(self, name: str) -> Any:
        return getattr(self._api, name)


class CourseraProvider:
    """Adapter around the small, focused `coursera-transcripts` package."""

    name = "coursera"

    def __init__(
        self,
        cauth: str,
        *,
        api_factory: Callable[[str], Any] | None = None,
        downloader_factory: Callable[..., Any] | None = None,
        console: Any | None = None,
    ) -> None:
        self._cauth = normalize_cauth(cauth)
        self._api_factory = api_factory
        self._downloader_factory = downloader_factory
        self._console = console

    def get_course_materials(self, slug: str) -> dict[str, Any]:
        """Return ordered course metadata for catalog construction."""

        if self._api_factory is None:
            from coursera_transcripts.api import CourseAPI

            api_factory = CourseAPI
        else:
            api_factory = self._api_factory
        api_options = {"console": self._console} if self._console is not None else {}
        api = api_factory(self._cauth, **api_options)
        return api.get_course_materials(slug)

    def fetch(self, request: FetchRequest) -> FetchResult:
        if self._api_factory is None or self._downloader_factory is None:
            from coursera_transcripts.api import CourseAPI
            from coursera_transcripts.cli import console as upstream_console
            from coursera_transcripts.downloader import TranscriptDownloader

            api_factory = CourseAPI
            downloader_factory = TranscriptDownloader
            console = self._console or upstream_console
        else:
            api_factory = self._api_factory
            downloader_factory = self._downloader_factory
            console = self._console

        api_options = {"console": console} if console is not None else {}
        downloader_options = {"console": console} if console is not None else {}

        api = _CatalogingAPI(api_factory(self._cauth, **api_options))
        downloader = downloader_factory(
            api=api,
            output_dir=request.output_dir,
            language=request.language,
            fmt=request.transcript_format.value,
            **downloader_options,
        )
        stats = downloader.fetch_all_transcripts(request.slug)

        if api.materials is not None:
            course_dir = request.output_dir / request.slug
            catalog = catalog_from_coursera_materials(
                request.slug,
                api.materials,
                course_dir,
            )
            save_catalog(catalog, course_dir)

        return FetchResult(
            provider=self.name,
            course_slug=request.slug,
            output_dir=request.output_dir / request.slug,
            downloaded=int(stats.get("success", 0)),
            skipped=int(stats.get("skipped", 0)),
            failed=int(stats.get("failed", 0)),
            total=int(stats.get("total", 0)),
        )
