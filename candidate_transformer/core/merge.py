"""Merge normalized source profiles into one canonical candidate."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import phonenumbers

from candidate_transformer.core.confidence import array_item_confidence, overall_confidence, scalar_confidence
from candidate_transformer.core.constants import SOURCE_PRIORITY
from candidate_transformer.core.experience import years_from_experience
from candidate_transformer.core.identity import candidate_id_for
from candidate_transformer.core.models import MergeResult, SourceIssue, SourceProfile


CANONICAL_TEMPLATE = {
    "candidate_id": None,
    "full_name": None,
    "emails": [],
    "phones": [],
    "location": {"city": None, "region": None, "country": None},
    "links": {"linkedin": None, "github": None, "portfolio": None, "others": []},
    "headline": None,
    "years_experience": None,
    "skills": [],
    "experience": [],
    "education": [],
    "provenance": [],
    "overall_confidence": 0.0,
}


def merge_profiles(identity_key: str, profiles: list[SourceProfile], run_date: date) -> MergeResult:
    """Merge one identity group into the assignment's canonical schema."""

    issues: list[SourceIssue] = [issue for profile in profiles for issue in profile.issues]
    canonical = _deep_copy(CANONICAL_TEMPLATE)
    canonical["candidate_id"] = candidate_id_for(identity_key)
    field_confidences: dict[str, float] = {}

    for field in ("full_name", "headline"):
        value, provenance, confidence, conflict = _choose_scalar(field, profiles)
        canonical[field] = value
        field_confidences[field] = confidence
        if provenance:
            canonical["provenance"].append(provenance)
        if conflict:
            issues.append(SourceIssue("merge", f"conflict on {field}; highest priority normalized value retained"))

    emails, email_prov, field_confidences["emails"] = _merge_simple_array("emails", profiles)
    canonical["emails"] = emails
    canonical["provenance"].extend(email_prov)

    phones, phone_prov, field_confidences["phones"] = _merge_simple_array("phones", profiles)
    canonical["phones"] = _dedupe_phones(phones, profiles)
    canonical["provenance"].extend(phone_prov)
    field_confidences["phones"] = field_confidences["phones"] if canonical["phones"] else 0.0

    canonical["location"], location_prov, field_confidences["location"] = _merge_location(profiles)
    canonical["provenance"].extend(location_prov)

    canonical["links"], link_prov, field_confidences["links"] = _merge_links(profiles)
    canonical["provenance"].extend(link_prov)

    canonical["skills"], skill_prov, field_confidences["skills"] = _merge_skills(profiles)
    canonical["provenance"].extend(skill_prov)

    for field in ("experience", "education"):
        values, provenance, confidence = _merge_dict_array(field, profiles)
        canonical[field] = values
        canonical["provenance"].extend(provenance)
        field_confidences[field] = confidence

    canonical["years_experience"] = years_from_experience(canonical["experience"], run_date)
    if canonical["years_experience"] is not None:
        canonical["provenance"].append({"field": "years_experience", "source": "merge", "method": "derived_from_experience"})
        field_confidences["years_experience"] = field_confidences.get("experience", 0.0)

    canonical["overall_confidence"] = overall_confidence(field_confidences)
    canonical["provenance"].sort(key=lambda item: (item["field"], item["source"], item["method"]))
    return MergeResult(canonical, tuple(issues))


def _choose_scalar(field: str, profiles: list[SourceProfile]) -> tuple[Any, dict[str, str] | None, float, bool]:
    candidates = [
        (profile.fields[field], profile)
        for profile in profiles
        if profile.fields.get(field) not in (None, "", [])
    ]
    if not candidates:
        return None, None, 0.0, False
    candidates.sort(key=lambda item: (SOURCE_PRIORITY.get(item[1].source_type, 99), item[1].source_id))
    chosen, chosen_profile = candidates[0]
    conflict = any(not _compatible_scalar(chosen, value) for value, _ in candidates[1:])
    provenance = {"field": field, "source": chosen_profile.source_id, "method": chosen_profile.method}
    confidence = scalar_confidence([(value, profile.reliability) for value, profile in candidates], conflict)
    return chosen, provenance, confidence, conflict


def _compatible_scalar(left: Any, right: Any) -> bool:
    lval = str(left).lower()
    rval = str(right).lower()
    return lval == rval or lval in rval or rval in lval


def _merge_simple_array(field: str, profiles: list[SourceProfile]) -> tuple[list[str], list[dict[str, str]], float]:
    merged: list[str] = []
    provenance: list[dict[str, str]] = []
    reliabilities: list[float] = []
    for profile in _priority_order(profiles):
        for value in profile.fields.get(field, []):
            if value not in merged:
                merged.append(value)
                provenance.append({"field": field, "source": profile.source_id, "method": profile.method})
            reliabilities.append(profile.reliability)
    return merged, provenance, array_item_confidence(reliabilities)


def _merge_location(profiles: list[SourceProfile]) -> tuple[dict[str, Any], list[dict[str, str]], float]:
    result = {"city": None, "region": None, "country": None}
    provenance: list[dict[str, str]] = []
    reliabilities: list[float] = []
    for key in result:
        for profile in _priority_order(profiles):
            value = (profile.fields.get("location") or {}).get(key)
            if value:
                result[key] = value
                provenance.append({"field": f"location.{key}", "source": profile.source_id, "method": profile.method})
                reliabilities.append(profile.reliability)
                break
    return result, provenance, array_item_confidence(reliabilities)


def _merge_links(profiles: list[SourceProfile]) -> tuple[dict[str, Any], list[dict[str, str]], float]:
    result = {"linkedin": None, "github": None, "portfolio": None, "others": []}
    provenance: list[dict[str, str]] = []
    reliabilities: list[float] = []
    for profile in _priority_order(profiles):
        links = profile.fields.get("links") or {}
        for key in ("linkedin", "github", "portfolio"):
            if not result[key] and links.get(key):
                result[key] = links[key]
                provenance.append({"field": f"links.{key}", "source": profile.source_id, "method": profile.method})
                reliabilities.append(profile.reliability)
        for other in links.get("others", []):
            if other not in result["others"]:
                result["others"].append(other)
                provenance.append({"field": "links.others", "source": profile.source_id, "method": profile.method})
                reliabilities.append(profile.reliability)
    return result, provenance, array_item_confidence(reliabilities)


def _merge_skills(profiles: list[SourceProfile]) -> tuple[list[dict[str, Any]], list[dict[str, str]], float]:
    by_name: dict[str, list[dict[str, Any]]] = {}
    for profile in _priority_order(profiles):
        for skill in profile.fields.get("skills", []):
            by_name.setdefault(skill["name"], []).append(skill)
    skills: list[dict[str, Any]] = []
    provenance: list[dict[str, str]] = []
    for name in sorted(by_name):
        evidence = by_name[name]
        confidence = array_item_confidence([item["base_confidence"] for item in evidence])
        sources = sorted({item["source"] for item in evidence})
        skills.append({"name": name, "confidence": confidence, "sources": sources})
        for item in evidence:
            provenance.append({"field": f"skills.{name}", "source": item["source"], "method": item["method"]})
    confidence = array_item_confidence([skill["confidence"] for skill in skills])
    return skills, provenance, confidence


def _merge_dict_array(field: str, profiles: list[SourceProfile]) -> tuple[list[dict[str, Any]], list[dict[str, str]], float]:
    key_fn = _experience_key if field == "experience" else _education_key
    merged_by_key: dict[tuple[str, ...], dict[str, Any]] = {}
    key_order: list[tuple[str, ...]] = []
    provenance: list[dict[str, str]] = []
    reliabilities: list[float] = []
    for profile in _priority_order(profiles):
        for item in profile.fields.get(field, []):
            semantic_key = key_fn(item)
            if not any(semantic_key):
                exact_key = tuple((name, item.get(name)) for name in sorted(item))
                if exact_key in merged_by_key:
                    continue
                semantic_key = exact_key
            if semantic_key in merged_by_key:
                merged_by_key[semantic_key] = _combine_records(merged_by_key[semantic_key], item)
            else:
                merged_by_key[semantic_key] = dict(item)
                key_order.append(semantic_key)
            provenance.append({"field": field, "source": profile.source_id, "method": profile.method})
            reliabilities.append(profile.reliability)
    return [merged_by_key[key] for key in key_order], provenance, array_item_confidence(reliabilities)


def _experience_key(item: dict[str, Any]) -> tuple[str, str]:
    return (_normalize_match_text(item.get("company")), _normalize_match_text(item.get("title")))


def _education_key(item: dict[str, Any]) -> tuple[str]:
    institution = _normalize_match_text(item.get("institution"))
    return (institution,) if institution else ()


def _normalize_match_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _combine_records(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    """Fill missing fields from a lower-priority source without overriding populated values."""

    result = dict(primary)
    for key, value in secondary.items():
        if value is None:
            continue
        if key not in result or result[key] is None:
            result[key] = value
            continue
        if key == "summary" and len(str(value)) > len(str(result[key])):
            result[key] = value
        elif key == "start" and _date_specificity(value) > _date_specificity(result[key]):
            result[key] = value
        elif key == "end" and _date_specificity(value) > _date_specificity(result.get(key)):
            result[key] = value
    return {key: value for key, value in result.items() if value is not None}


def _dedupe_phones(phones: list[str], profiles: list[SourceProfile]) -> list[str]:
    """Collapse E.164 variants that share the same national number, preferring location hints."""

    if not phones:
        return []
    country_hints = {
        (profile.fields.get("location") or {}).get("country")
        for profile in profiles
        if (profile.fields.get("location") or {}).get("country")
    }
    grouped: dict[str, list[str]] = {}
    for phone in phones:
        parsed = phonenumbers.parse(phone, None)
        grouped.setdefault(str(parsed.national_number), []).append(phone)
    deduped: list[str] = []
    for national_number in sorted(grouped):
        candidates = grouped[national_number]
        deduped.append(candidates[0] if len(candidates) == 1 else _pick_best_phone(candidates, country_hints))
    return deduped


def _pick_best_phone(candidates: list[str], country_hints: set[str]) -> str:
    if country_hints:
        for phone in sorted(candidates):
            region = phonenumbers.region_code_for_number(phonenumbers.parse(phone, None))
            if region in country_hints:
                return phone
    return sorted(candidates)[0]


def _date_specificity(value: Any) -> int:
    if value is None:
        return 0
    text = str(value)
    if re.fullmatch(r"\d{4}-\d{2}", text):
        return 2
    if re.fullmatch(r"\d{4}", text):
        return 1
    return 0


def _priority_order(profiles: list[SourceProfile]) -> list[SourceProfile]:
    return sorted(profiles, key=lambda profile: (SOURCE_PRIORITY.get(profile.source_type, 99), profile.source_id))


def _deep_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _deep_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_deep_copy(item) for item in value]
    return value
