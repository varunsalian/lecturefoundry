"""YouTube playlist caption importer powered by yt-dlp."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from lecturefoundry.catalog import (
    CATALOG_FILENAME,
    CourseCatalog,
    LectureRecord,
    ModuleRecord,
    load_catalog,
    save_catalog,
    slugify,
)
from lecturefoundry.models import FetchResult, PlaylistFetchRequest


class YouTubeProviderError(RuntimeError):
    """A playlist could not be imported safely."""


class YouTubeProvider:
    """Import uploaded or automatic captions without downloading media."""

    name = "youtube"

    def __init__(
        self,
        *,
        ydl_factory: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        self._ydl_factory = ydl_factory

    def fetch(self, request: PlaylistFetchRequest) -> FetchResult:
        ydl_factory = self._ydl_factory
        if ydl_factory is None:
            from yt_dlp import YoutubeDL

            ydl_factory = YoutubeDL

        options = {
            "extract_flat": False,
            "ignoreerrors": True,
            "noplaylist": False,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 20,
            "skip_download": True,
        }
        if request.max_videos is not None:
            options["playlistend"] = request.max_videos
        try:
            with ydl_factory(options) as ydl:
                playlist = ydl.extract_info(request.url, download=False)
                return self._save_playlist(ydl, playlist, request)
        except YouTubeProviderError:
            raise
        except Exception as error:
            raise YouTubeProviderError(
                f"YouTube playlist extraction failed: {error}"
            ) from error

    def _save_playlist(
        self,
        ydl: Any,
        playlist: Any,
        request: PlaylistFetchRequest,
    ) -> FetchResult:
        if not isinstance(playlist, dict):
            raise YouTubeProviderError("YouTube returned no playlist metadata")
        raw_entries_value = playlist.get("entries")
        if raw_entries_value is None:
            raise YouTubeProviderError("The URL does not contain a playlist")

        raw_entries = list(raw_entries_value)
        if request.max_videos is not None:
            raw_entries = raw_entries[: request.max_videos]
        entries = [entry for entry in raw_entries if isinstance(entry, dict)]
        entries.sort(key=_playlist_position)
        if not entries:
            raise YouTubeProviderError("The playlist contains no available videos")

        title = str(playlist.get("title") or "YouTube playlist").strip()
        playlist_id = _playlist_id(playlist, request.url)
        course_slug = (
            _bounded_slug(request.course_slug)
            if request.course_slug
            else _find_course_slug(request.output_dir, playlist_id)
            or _playlist_course_slug(title, playlist_id)
        )
        course_dir = request.output_dir / course_slug
        transcript_dir = course_dir / "01-videos"

        existing_catalog = _existing_youtube_catalog(course_dir, playlist_id)
        transcript_dir.mkdir(parents=True, exist_ok=True)
        existing_lectures = (
            tuple(
                lecture
                for module in existing_catalog.modules
                for lecture in module.lectures
            )
            if existing_catalog is not None
            else ()
        )
        existing_by_source = {
            lecture.source_id: lecture
            for lecture in existing_lectures
            if lecture.source_id
        }

        lectures: list[LectureRecord] = []
        downloaded = 0
        skipped = 0
        failed = len(raw_entries) - len(entries)
        warnings: list[str] = []
        used_lecture_numbers = {lecture.number for lecture in existing_lectures}
        emitted_sources: set[str] = set()
        selected_lecture_numbers: list[int] = []
        source_occurrences: dict[str, int] = {}
        if failed:
            warnings.append(
                f"Skipped {failed} unavailable or deleted playlist entries"
            )

        for fallback_number, entry in enumerate(entries, 1):
            video_id = str(entry.get("id") or "").strip()
            video_title = str(entry.get("title") or video_id or "Untitled video").strip()
            if not video_id:
                failed += 1
                warnings.append("Skipped a playlist entry with no video ID")
                continue

            occurrence = source_occurrences.get(video_id, 0) + 1
            source_occurrences[video_id] = occurrence
            source_id = video_id if occurrence == 1 else f"{video_id}#{occurrence}"
            existing = existing_by_source.get(source_id)
            lecture_number = (
                existing.number
                if existing is not None
                else _stable_lecture_number(
                    entry,
                    fallback_number,
                    used_lecture_numbers,
                )
            )
            used_lecture_numbers.add(lecture_number)
            emitted_sources.add(source_id)
            lecture_slug = (
                existing.slug
                if existing is not None
                else _video_slug(video_title, source_id)
            )
            relative_path = (
                Path(existing.transcript)
                if existing is not None and existing.transcript
                else Path("01-videos") / f"{lecture_number:02d}-{lecture_slug}.txt"
            )
            transcript_path = _safe_course_path(course_dir, relative_path)

            if transcript_path.is_file() and not request.force:
                skipped += 1
            else:
                caption = _select_caption(entry, request.language)
                if caption is None:
                    failed += 1
                    warnings.append(
                        f"{video_title}: no {request.language!r} captions available"
                    )
                    if existing is not None and transcript_path.is_file():
                        lectures.append(
                            _updated_lecture(existing, video_title, source_id)
                        )
                        selected_lecture_numbers.append(existing.number)
                    continue
                try:
                    payload = _download_caption(ydl, caption)
                    transcript = caption_to_text(payload, str(caption.get("ext") or ""))
                except Exception as error:
                    failed += 1
                    warnings.append(
                        f"{video_title}: caption download failed ({error})"
                    )
                    if existing is not None and transcript_path.is_file():
                        lectures.append(
                            _updated_lecture(existing, video_title, source_id)
                        )
                        selected_lecture_numbers.append(existing.number)
                    continue
                if not transcript:
                    failed += 1
                    warnings.append(f"{video_title}: captions were empty")
                    if existing is not None and transcript_path.is_file():
                        lectures.append(
                            _updated_lecture(existing, video_title, source_id)
                        )
                        selected_lecture_numbers.append(existing.number)
                    continue
                _write_text_atomic(transcript_path, transcript + "\n")
                downloaded += 1

            lectures.append(
                LectureRecord(
                    number=lecture_number,
                    title=video_title,
                    slug=lecture_slug,
                    transcript=str(relative_path),
                    source_id=source_id,
                )
            )
            selected_lecture_numbers.append(lecture_number)

        preserved = [
            lecture
            for lecture in existing_lectures
            if lecture.source_id not in emitted_sources
        ]
        if preserved:
            lectures.extend(preserved)
            warnings.append(
                f"Preserved {len(preserved)} previously imported lecture(s) not "
                "present in this partial extraction"
            )

        if not lectures:
            raise YouTubeProviderError(
                f"No {request.language!r} captions were available in this playlist"
            )

        save_catalog(
            CourseCatalog(
                course_slug=course_slug,
                modules=(
                    ModuleRecord(
                        number=1,
                        title="Videos",
                        slug="videos",
                        lectures=tuple(lectures),
                    ),
                ),
                version=2,
                source_provider="youtube",
                source_id=playlist_id,
                source_url=request.url,
                title=title,
            ),
            course_dir,
        )
        return FetchResult(
            provider=self.name,
            course_slug=course_slug,
            output_dir=course_dir,
            downloaded=downloaded,
            skipped=skipped,
            failed=failed,
            total=len(raw_entries),
            warnings=tuple(warnings),
            lecture_keys=tuple(
                (1, lecture_number) for lecture_number in selected_lecture_numbers
            ),
        )


def _playlist_position(entry: dict[str, Any]) -> tuple[int, str]:
    position = entry.get("playlist_index")
    try:
        number = int(position)
    except (TypeError, ValueError):
        number = 1_000_000
    return (number, str(entry.get("id") or ""))


def _stable_lecture_number(
    entry: dict[str, Any],
    fallback: int,
    used: set[int],
) -> int:
    try:
        number = int(entry.get("playlist_index"))
    except (TypeError, ValueError):
        number = fallback
    if number < 1 or number in used:
        number = fallback
        while number in used:
            number += 1
    return number


def _bounded_slug(value: str, maximum: int = 80) -> str:
    return slugify(value)[:maximum].rstrip("-") or "untitled"


def _playlist_id(playlist: dict[str, Any], url: str) -> str:
    playlist_id = str(playlist.get("id") or "").strip()
    if not playlist_id:
        playlist_id = parse_qs(urlparse(url).query).get("list", [""])[0].strip()
    if not playlist_id:
        raise YouTubeProviderError("YouTube returned no stable playlist ID")
    return playlist_id


def _identity_suffix(prefix: str, source_id: str, maximum: int = 32) -> str:
    readable = slugify(source_id)[:maximum].rstrip("-") or "item"
    digest = hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{readable}-{digest}"


def _playlist_course_slug(title: str, playlist_id: str) -> str:
    suffix = _identity_suffix("yt", playlist_id)
    title_length = max(1, 80 - len(suffix) - 1)
    return f"{_bounded_slug(title, title_length)}-{suffix}"


def _find_course_slug(output_dir: Path, playlist_id: str) -> str | None:
    matches: list[str] = []
    if not output_dir.is_dir():
        return None
    for catalog_path in output_dir.glob(f"*/{CATALOG_FILENAME}"):
        try:
            catalog = load_catalog(catalog_path.parent)
        except (KeyError, OSError, TypeError, ValueError):
            continue
        if catalog.source_provider == "youtube" and catalog.source_id == playlist_id:
            matches.append(catalog_path.parent.name)
    if len(matches) > 1:
        raise YouTubeProviderError(
            f"Multiple local courses reference YouTube playlist {playlist_id}; "
            "select one with --slug"
        )
    return matches[0] if matches else None


def _video_slug(title: str, source_id: str) -> str:
    suffix = _identity_suffix("yt", source_id, maximum=20)
    title_length = max(1, 80 - len(suffix) - 1)
    return f"{_bounded_slug(title, title_length)}-{suffix}"


def _existing_youtube_catalog(
    course_dir: Path,
    playlist_id: str,
) -> CourseCatalog | None:
    if not (course_dir / CATALOG_FILENAME).is_file():
        return None
    catalog = load_catalog(course_dir)
    if catalog.source_provider != "youtube" or catalog.source_id != playlist_id:
        source = (
            f"{catalog.source_provider}:{catalog.source_id}"
            if catalog.source_provider or catalog.source_id
            else "an unidentified existing course"
        )
        raise YouTubeProviderError(
            f"Output folder {course_dir} already belongs to {source}; "
            "choose a different --slug"
        )
    return catalog


def _updated_lecture(
    lecture: LectureRecord,
    title: str,
    source_id: str,
) -> LectureRecord:
    return LectureRecord(
        number=lecture.number,
        title=title,
        slug=lecture.slug,
        transcript=lecture.transcript,
        source_id=source_id,
    )


def _safe_course_path(course_dir: Path, relative_path: Path) -> Path:
    course_root = course_dir.resolve()
    path = (course_dir / relative_path).resolve()
    if path == course_root or course_root not in path.parents:
        raise YouTubeProviderError(
            f"Catalog transcript path escapes the course folder: {relative_path}"
        )
    return path


def _language_keys(tracks: dict[str, Any], requested: str) -> Iterable[str]:
    requested = requested.lower().replace("_", "-")
    normalized = {key.lower().replace("_", "-"): key for key in tracks}
    if requested in normalized:
        yield normalized[requested]
    base = requested.split("-", 1)[0]
    if base in normalized and base != requested:
        yield normalized[base]
    prefix = base + "-"
    for normalized_key, original_key in normalized.items():
        if normalized_key.startswith(prefix) and normalized_key != requested:
            yield original_key


def _select_caption(entry: dict[str, Any], language: str) -> dict[str, Any] | None:
    for source_name in ("subtitles", "automatic_captions"):
        tracks = entry.get(source_name)
        if not isinstance(tracks, dict):
            continue
        for key in _language_keys(tracks, language):
            formats = tracks.get(key)
            if not isinstance(formats, list):
                continue
            supported = [
                item
                for item in formats
                if isinstance(item, dict)
                and item.get("url")
                and str(item.get("ext") or "").lower()
                in {"json3", "vtt", "srt", "ttml", "srv3"}
            ]
            if supported:
                priority = {"json3": 0, "vtt": 1, "srt": 2, "ttml": 3, "srv3": 4}
                supported.sort(key=lambda item: priority[str(item["ext"]).lower()])
                return supported[0]
    return None


def _download_caption(ydl: Any, caption: dict[str, Any]) -> str:
    response = ydl.urlopen(str(caption["url"]))
    try:
        payload = response.read()
    finally:
        response.close()
    if isinstance(payload, str):
        return payload
    return payload.decode("utf-8-sig", errors="replace")


def caption_to_text(payload: str, extension: str) -> str:
    """Convert a supported caption payload into deduplicated plain text."""

    extension = extension.lower()
    if extension == "json3":
        return _json3_text(payload)
    if extension in {"ttml", "srv3"}:
        return _xml_text(payload)
    if extension in {"vtt", "srt"}:
        return _timed_text(payload)
    raise ValueError(f"Unsupported caption format: {extension}")


def _json3_text(payload: str) -> str:
    data = json.loads(payload)
    cues = []
    for event in data.get("events", []):
        segments = event.get("segs", []) if isinstance(event, dict) else []
        cue = "".join(
            str(segment.get("utf8") or "")
            for segment in segments
            if isinstance(segment, dict)
        )
        if cue.strip():
            cues.append(cue)
    return _merge_cues(cues)


def _xml_text(payload: str) -> str:
    root = ET.fromstring(payload)
    cues = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] in {"p", "text"}:
            cue = "".join(element.itertext())
            if cue.strip():
                cues.append(cue)
    return _merge_cues(cues)


_TIMESTAMP = re.compile(
    r"^\s*(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3}\s*-->\s*"
    r"(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3}"
)
_INLINE_TIMESTAMP = re.compile(r"<\d{2}:\d{2}:\d{2}[.]\d{3}>")
_TAG = re.compile(r"<[^>]+>")


def _timed_text(payload: str) -> str:
    cues = []
    for block in re.split(r"\r?\n\s*\r?\n", payload):
        lines = []
        for line in block.splitlines():
            stripped = line.strip()
            if (
                not stripped
                or stripped == "WEBVTT"
                or stripped.isdigit()
                or stripped.startswith(("Kind:", "Language:", "NOTE"))
                or _TIMESTAMP.match(stripped)
            ):
                continue
            clean = _TAG.sub("", _INLINE_TIMESTAMP.sub("", stripped))
            clean = html.unescape(clean).strip()
            if clean:
                lines.append(clean)
        if lines:
            cues.append(" ".join(lines))
    return _merge_cues(cues)


def _merge_cues(cues: Iterable[str]) -> str:
    words: list[str] = []
    for cue in cues:
        cue_words = re.sub(r"\s+", " ", cue).strip().split(" ")
        if not cue_words:
            continue
        overlap = min(len(words), len(cue_words))
        while overlap and words[-overlap:] != cue_words[:overlap]:
            overlap -= 1
        words.extend(cue_words[overlap:])
    return " ".join(words).strip()


def _write_text_atomic(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(contents)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
