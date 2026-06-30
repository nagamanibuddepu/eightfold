"""Resume parser adapter using pdfplumber PDF text extraction."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pdfplumber

from candidate_transformer.core.constants import SOURCE_RELIABILITY
from candidate_transformer.core.models import SourceIssue, SourceProfile

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(
    r"(?:\+\d[\d\s().-]{7,}\d|\b[6-9]\d{9}\b|\b\d{3}[\s.-]\d{3}[\s.-]\d{4}\b)"
)
SECTION_HEADER = re.compile(r"^(skills|experience|education|profile|summary|headline)\b", re.IGNORECASE)
SECTION_NAMES = (
    "skills",
    "experience",
    "education",
    "profile",
    "summary",
    "headline",
    "achievements",
    "projects",
    "certifications",
    "codingprofiles",
)


def parse_resume(path: str) -> list[SourceProfile]:
    source_id = f"resume:{path}"
    try:
        text = _clean_pdf_text(_read_resume_text(path))
    except (OSError, ValueError, RuntimeError) as exc:
        return [_error_profile(source_id, f"could not read resume: {exc}")]

    if not text.strip():
        return [_error_profile(source_id, "resume is empty")]

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    fields = {
        "full_name": _guess_name(lines),
        "emails": _extract_emails(text),
        "phones": _extract_phones(text),
        "headline": _extract_label(text, "headline") or _guess_headline(lines),
        "skills": _extract_skills(text),
        "experience": _extract_experience(text),
        "education": _extract_education(text),
        "links": _extract_links(text),
    }

    return [
        SourceProfile(
            source_id=source_id,
            source_type="resume",
            reliability=SOURCE_RELIABILITY["resume"],
            method="resume_pdf_parse",
            fields=fields,
        )
    ]


def _read_resume_text(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix != ".pdf":
        raise OSError("unsupported resume format; use PDF")
    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    text = "\n".join(pages)
    if not text.strip():
        raise RuntimeError("pdfplumber extracted no text from resume PDF")
    return text


def _clean_pdf_text(text: str) -> str:
    return re.sub(r"\(cid:\d+\)", "", text)


def _extract_emails(text: str) -> list[str]:
    return sorted(set(EMAIL_PATTERN.findall(text)))


def _extract_phones(text: str) -> list[str]:
    phones = PHONE_PATTERN.findall(text)
    return sorted({phone.strip() for phone in phones})


def _guess_name(lines: list[str]) -> str | None:
    for line in lines[:4]:
        lowered = line.lower()
        if lowered.startswith("email") or lowered.startswith("phone") or "@" in line or "|" in line:
            continue
        words = line.split()
        if 2 <= len(words) <= 4 and not SECTION_HEADER.match(line):
            return _title_name(line)
    return None


def _title_name(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split())


def _extract_label(text: str, label: str) -> str | None:
    match = re.search(rf"{label}\s*[:\-]\s*(.+)", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _guess_headline(lines: list[str]) -> str | None:
    for line in lines[1:4]:
        if SECTION_HEADER.match(line) or _looks_like_contact_line(line):
            continue
        return line
    return None


def _looks_like_contact_line(line: str) -> bool:
    lowered = line.lower()
    return "@" in line or "|" in line or "github" in lowered or "linkedin" in lowered or "portfolio" in lowered


def _extract_skills(text: str) -> list[str]:
    match = re.search(r"skills?\s*[:\-]\s*(.+)", text, flags=re.IGNORECASE)
    if match:
        return [item.strip() for item in re.split(r",|;", match.group(1)) if item.strip()]

    section = _extract_section(text, "skills")
    if not section:
        return []

    skills: list[str] = []
    for line in section.splitlines():
        if ":" not in line:
            continue
        _, values = line.split(":", 1)
        for item in re.split(r",|;", values):
            cleaned = item.strip()
            if cleaned and len(cleaned) <= 40:
                skills.append(cleaned)
    return skills


def _extract_links(text: str) -> dict[str, Any]:
    links: dict[str, Any] = {"others": []}
    github = re.search(r"https?://github\.com/[A-Za-z0-9-]+", text)
    if github:
        links["github"] = github.group(0)
    linkedin = re.search(r"https?://(?:www\.)?linkedin\.com/[A-Za-z0-9\-/]+", text)
    if linkedin:
        links["linkedin"] = linkedin.group(0)
    portfolio = re.search(r"https?://[\w\-\.]+\.[a-z]{2,6}(/[\w\-\./]*)?", text)
    if portfolio:
        url = portfolio.group(0)
        if not (github and url == github.group(0)) and not (linkedin and url == linkedin.group(0)):
            links["portfolio"] = url
    return links


def _extract_experience(text: str) -> list[dict[str, Any]]:
    section = _extract_section(text, "experience")
    if not section:
        return []
    experiences = []
    for line in section.splitlines():
        line = line.strip()
        if not line or line.startswith("•"):
            continue
        parts = [part.strip() for part in re.split(r"\s+[\u2013\u2014\-]\s+", line) if part.strip()]
        if len(parts) >= 4:
            experiences.append({"company": parts[0], "title": parts[1], "start": parts[2], "end": parts[3]})
        elif len(parts) == 3:
            start, end = _parse_dates(parts[2])
            experiences.append({"company": parts[0], "title": parts[1], "start": start, "end": end})
    return experiences


def _extract_education(text: str) -> list[dict[str, Any]]:
    section = _extract_section(text, "education")
    if not section:
        return []

    education: list[dict[str, Any]] = []
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    if not lines:
        return education

    year_match = re.search(r"(\d{4})\s*[–—-]\s*(\d{4})", lines[0])
    institution = re.sub(r"\s*\d{4}.*", "", lines[0]).strip()
    item: dict[str, Any] = {"institution": institution}
    if year_match:
        item["end_year"] = int(year_match.group(2))
    if len(lines) > 1:
        degree_match = re.search(r"(B\.?Tech[^|]*)", lines[1], flags=re.IGNORECASE)
        if degree_match:
            item["degree"] = degree_match.group(1).strip()
            field_match = re.search(r"\(([^)]+)\)", lines[1])
            if field_match:
                item["field"] = field_match.group(1).strip()
    if item.get("institution"):
        education.append(item)
    return education


def _parse_dates(value: str) -> tuple[str | None, str | None]:
    parts = [part.strip() for part in re.split(r"to|–|—|-", value, flags=re.IGNORECASE) if part.strip()]
    if not parts:
        return None, None
    return parts[0], parts[1] if len(parts) > 1 else None


def _extract_section(text: str, header: str) -> str | None:
    other_headers = "|".join(name for name in SECTION_NAMES if name != header.lower())
    pattern = re.compile(
        rf"(?:^|\n){header}\s*:?\s*\n(.+?)(?=\n(?:{other_headers})\s*:?\s*(?:\n|$)|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _error_profile(source_id: str, message: str) -> SourceProfile:
    return SourceProfile(source_id, "resume", SOURCE_RELIABILITY["resume"], "read_error", {}, (SourceIssue(source_id, message),))
