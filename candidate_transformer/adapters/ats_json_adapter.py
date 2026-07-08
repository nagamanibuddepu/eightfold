"""ATS JSON adapter for semi-structured candidate blobs."""

from __future__ import annotations

import json
from typing import Any

from candidate_transformer.core.constants import SOURCE_RELIABILITY
from candidate_transformer.core.models import SourceIssue, SourceProfile


def parse_ats_json(path: str) -> list[SourceProfile]:
    """Parse ATS JSON for either candidate-style or publication-style payloads."""

    source_id = f"ats_json:{path}"
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return [_error_profile(source_id, f"could not parse ATS JSON: {exc}")]

    if not isinstance(data, (dict, list)):
        return [_error_profile(source_id, "ATS JSON root must be an object or array")]

    records = data if isinstance(data, list) else [data]
    profiles: list[SourceProfile] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            profiles.append(_error_profile(f"{source_id}#{index}", "ATS record is not an object"))
            continue
        if _looks_like_publication_export(record):
            profiles.append(_publication_profile(source_id, index, record))
        else:
            profiles.append(_candidate_profile(source_id, index, record))
    return profiles


def _looks_like_publication_export(record: dict[str, Any]) -> bool:
    return isinstance(record.get("papers"), list) or "author_metrics" in record or record.get("source") == "arxiv_author_export"


def _candidate_profile(source_id: str, index: int, record: dict[str, Any]) -> SourceProfile:
    return SourceProfile(
        source_id=f"{source_id}#{index}",
        source_type="ats_json",
        reliability=SOURCE_RELIABILITY["ats_json"],
        method="ats_field_mapping",
        fields={
            "full_name": record.get("candidateName"),
            "emails": _as_list(record.get("contact", {}).get("email") if isinstance(record.get("contact"), dict) else None),
            "phones": _as_list(record.get("contact", {}).get("mobile") if isinstance(record.get("contact"), dict) else None),
            "location": {
                "city": record.get("city"),
                "region": record.get("state"),
                "country": record.get("country"),
            },
            "links": {
                "linkedin": record.get("linkedinUrl"),
                "github": record.get("githubUrl"),
                "portfolio": record.get("portfolioUrl"),
            },
            "headline": record.get("currentTitle"),
            "skills": _as_list(record.get("skillTags")),
            "experience": _map_experience(record.get("workHistory")),
            "education": _map_education(record.get("schools") or record.get("college")),
        },
    )


def _publication_profile(source_id: str, index: int, record: dict[str, Any]) -> SourceProfile:
    return SourceProfile(
        source_id=f"{source_id}#{index}",
        source_type="ats_json",
        reliability=SOURCE_RELIABILITY["ats_json"],
        method="publication_export_mapping",
        fields={
            "full_name": record.get("queried_author") or record.get("candidateName"),
            "emails": [],
            "phones": [],
            "location": {"city": None, "region": None, "country": None},
            "links": {},
            "headline": None,
            "skills": [],
            "experience": [],
            "education": [],
            "publications": _map_publications(record.get("papers")),
        },
    )


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _map_experience(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        {
            "company": item.get("employer"),
            "title": item.get("role"),
            "start": item.get("from"),
            "end": item.get("to"),
            "summary": item.get("description"),
        }
        for item in value
        if isinstance(item, dict)
    ]


def _map_education(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        {
            "institution": item.get("school") or item.get("college"),
            "degree": item.get("degree"),
            "field": item.get("major"),
            "end_year": item.get("graduationYear"),
        }
        for item in value
        if isinstance(item, dict)
    ]


def _map_publications(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    publications: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        publications.append(
            {
                "title": item.get("title"),
                "arxiv_id": item.get("arxiv_id"),
                "published": item.get("published"),
                "author_position": item.get("author_position"),
                "authors": item.get("authors"),
                "categories": _as_list(item.get("categories")),
                "topics": _as_list(item.get("topics")),
                "abstract": item.get("abstract"),
                "doi": item.get("doi"),
            }
        )
    return publications


def _error_profile(source_id: str, message: str) -> SourceProfile:
    return SourceProfile(source_id, "ats_json", SOURCE_RELIABILITY["ats_json"], "read_error", {}, (SourceIssue(source_id, message),))
