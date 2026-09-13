"""Application services shared by command-line and future UI adapters."""

from .fetch import fetch_transcripts
from .generate import (
    CourseNotesRequest,
    CourseNotesResult,
    NoteGenerationFailure,
    generate_course_notes,
)

__all__ = [
    "CourseNotesRequest",
    "CourseNotesResult",
    "NoteGenerationFailure",
    "fetch_transcripts",
    "generate_course_notes",
]
