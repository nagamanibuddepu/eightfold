"""Normalization functions that operate on one source at a time."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import phonenumbers
import pycountry
from dateutil import parser as date_parser

from candidate_transformer.core.constants import SKILL_ALIASES
from candidate_transformer.core.models import SourceIssue, SourceProfile


def normalize_email(value: str) -> str | None:
    """Return a lowercase email when the input is syntactically plausible."""

    cleaned = value.strip().lower()
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", cleaned):
        return cleaned
    return None


def normalize_phone(value: str, default_region: str = "US") -> str | None:
    """Return a phone number in E.164 format, or None when parsing fails."""

    try:
        parsed = phonenumbers.parse(value, None if value.strip().startswith("+") else default_region)
    except phonenumbers.NumberParseException:
        return None
    if phonenumbers.is_possible_number(parsed) and phonenumbers.is_valid_number(parsed):
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    return None


def normalize_country(value: str | None) -> str | None:
    """Return an ISO-3166 alpha-2 country code for common country names/codes."""

    if not value:
        return None
    cleaned = value.strip()
    if len(cleaned) == 2 and pycountry.countries.get(alpha_2=cleaned.upper()):
        return cleaned.upper()
    match = pycountry.countries.get(name=cleaned)
    if match:
        return match.alpha_2
    try:
        return pycountry.countries.search_fuzzy(cleaned)[0].alpha_2
    except LookupError:
        return None


def normalize_date_month(value: str | None, dayfirst: bool = False) -> str | None:
    """Normalize human dates to YYYY-MM while preserving unknowns as None."""

    if not value:
        return None
    text = value.strip()
    if text.lower() in {"present", "current", "now"}:
        return None
    try:
        parsed = date_parser.parse(text, default=date(1900, 1, 1), dayfirst=dayfirst)
    except (ValueError, OverflowError):
        return None
    return f"{parsed.year:04d}-{parsed.month:02d}"


def canonical_skill(value: str) -> tuple[str | None, str]:
    """Normalize skill spelling with a small deterministic alias map."""

    cleaned = re.sub(r"\s+", " ", value.strip().lower())
    if not cleaned:
        return None, "failed_normalization"
    return SKILL_ALIASES.get(cleaned, cleaned), "skill_alias" if cleaned in SKILL_ALIASES else "skill_passthrough"


def normalize_source_profile(profile: SourceProfile, default_region: str = "US") -> SourceProfile:
    """Normalize one source profile without depending on any merged state."""

    fields = dict(profile.fields)
    issues: list[SourceIssue] = list(profile.issues)

    fields["emails"] = _normalize_many(fields.get("emails", []), normalize_email)

    location = dict(fields["location"]) if isinstance(fields.get("location"), dict) else {}
    location["country"] = normalize_country(location.get("country"))
    fields["location"] = {key: value for key, value in location.items() if value}
    phone_region = location.get("country") or default_region
    fields["phones"] = _normalize_many(fields.get("phones", []), lambda phone: normalize_phone(phone, phone_region))

    fields["links"] = _normalize_links(fields.get("links", {}))
    fields["skills"] = _normalize_skills(fields.get("skills", []), profile)
    fields["experience"] = [_normalize_experience(item) for item in fields.get("experience", []) if isinstance(item, dict)]
    fields["education"] = [_normalize_education(item) for item in fields.get("education", []) if isinstance(item, dict)]

    if profile.source_type != "github" and not fields.get("emails") and not fields.get("phones"):
        issues.append(SourceIssue(profile.source_id, "source has no usable email or phone for identity matching"))

    return SourceProfile(profile.source_id, profile.source_type, profile.reliability, profile.method, fields, tuple(issues))


def _normalize_many(values: list[Any], normalizer: Any) -> list[str]:
    normalized: list[str] = []
    for value in values:
        result = normalizer(str(value))
        if result and result not in normalized:
            normalized.append(result)
    return normalized


def _normalize_links(links: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {"others": []}
    for key, value in links.items():
        if not value:
            continue
        if key == "others" and isinstance(value, list):
            normalized["others"].extend(_clean_url(item) for item in value if item)
        else:
            normalized[key] = _clean_url(str(value))
    normalized["others"] = sorted(set(item for item in normalized["others"] if item))
    return {key: value for key, value in normalized.items() if value}


def _clean_url(value: str) -> str:
    stripped = value.strip().rstrip("/")
    return stripped.replace("http://", "https://")


def _normalize_skills(values: list[Any], profile: SourceProfile) -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in values:
        name, method = canonical_skill(str(raw))
        if name and name not in seen:
            seen.add(name)
            skills.append({"name": name, "source": profile.source_id, "method": method, "base_confidence": profile.reliability})
    return skills


def _normalize_experience(item: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "company": _clean_text(item.get("company")),
        "title": _clean_text(item.get("title")),
        "start": normalize_date_month(item.get("start")),
        "end": normalize_date_month(item.get("end")),
        "summary": _clean_text(item.get("summary")),
    }
    return {key: value for key, value in normalized.items() if value is not None}


def _normalize_education(item: dict[str, Any]) -> dict[str, Any]:
    end_year = item.get("end_year")
    if isinstance(end_year, str) and end_year.strip().isdigit():
        end_year = int(end_year.strip())
    normalized = {
        "institution": _clean_text(item.get("institution")),
        "degree": _clean_text(item.get("degree")),
        "field": _clean_text(item.get("field")),
        "end_year": end_year if isinstance(end_year, int) else None,
    }
    return {key: value for key, value in normalized.items() if value is not None}


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value).strip())
    return cleaned or None
