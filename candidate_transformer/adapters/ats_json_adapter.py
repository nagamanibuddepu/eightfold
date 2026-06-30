"""ATS JSON adapter for semi-structured candidate blobs."""

from __future__ import annotations

import json
from typing import Any

from candidate_transformer.core.constants import SOURCE_RELIABILITY
from candidate_transformer.core.models import SourceIssue, SourceProfile


def parse_ats_json(path: str) -> list[SourceProfile]:
    """Parse ATS JSON whose field names do not match the canonical schema."""

    source_id = f"ats_json:{path}"
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return [_error_profile(source_id, f"could not parse ATS JSON: {exc}")]

    records = data if isinstance(data, list) else [data]
    profiles: list[SourceProfile] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            profiles.append(_error_profile(f"{source_id}#{index}", "ATS record is not an object"))
            continue
        profiles.append(
            SourceProfile(
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
        )
    return profiles


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


def _error_profile(source_id: str, message: str) -> SourceProfile:
    return SourceProfile(source_id, "ats_json", SOURCE_RELIABILITY["ats_json"], "read_error", {}, (SourceIssue(source_id, message),))
