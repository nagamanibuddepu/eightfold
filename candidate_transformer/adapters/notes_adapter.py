"""Recruiter notes adapter for free-text candidate notes."""

from __future__ import annotations

import re

from candidate_transformer.core.constants import SOURCE_RELIABILITY
from candidate_transformer.core.models import SourceIssue, SourceProfile


def parse_recruiter_notes(path: str) -> list[SourceProfile]:
    """Extract conservative candidate facts from recruiter notes text."""

    source_id = f"recruiter_notes:{path}"
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        return [_error_profile(source_id, f"could not read notes: {exc}")]

    if not text.strip():
        return [_error_profile(source_id, "notes file is empty")]

    skills = []
    skills_match = re.search(r"skills?\s*:\s*(.+)", text, flags=re.IGNORECASE)
    if skills_match:
        skills = [part.strip() for part in re.split(r",|;", skills_match.group(1)) if part.strip()]

    location = {}
    location_match = re.search(r"location\s*:\s*(.+)", text, flags=re.IGNORECASE)
    if location_match:
        pieces = [piece.strip() for piece in location_match.group(1).split(",")]
        if pieces:
            location["city"] = pieces[0]
        if len(pieces) > 1:
            location["country"] = pieces[-1]

    return [
        SourceProfile(
            source_id=source_id,
            source_type="recruiter_notes",
            reliability=SOURCE_RELIABILITY["recruiter_notes"],
            method="regex_note_extraction",
            fields={
                "emails": re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text),
                "phones": re.findall(r"(?:\+\d[\d\s().-]{7,}\d|\b\d{3}[\s.-]\d{3}[\s.-]\d{4}\b)", text),
                "skills": skills,
                "location": location,
                "headline": _match_line(text, "headline"),
            },
        )
    ]


def _match_line(text: str, label: str) -> str | None:
    match = re.search(rf"{label}\s*:\s*(.+)", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _error_profile(source_id: str, message: str) -> SourceProfile:
    return SourceProfile(source_id, "recruiter_notes", SOURCE_RELIABILITY["recruiter_notes"], "read_error", {}, (SourceIssue(source_id, message),))
