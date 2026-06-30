"""Deterministic identity resolution for normalized source profiles."""

from __future__ import annotations

import hashlib
import re

from candidate_transformer.core.models import SourceIssue, SourceProfile


def identity_key(profile: SourceProfile) -> str | None:
    """Return the strongest deterministic identity key available in one source."""

    emails = profile.fields.get("emails") or []
    if emails:
        return f"email:{emails[0]}"
    full_name = profile.fields.get("full_name")
    phones = profile.fields.get("phones") or []
    if full_name and phones:
        return f"name_phone:{_normalize_name(full_name)}|{phones[0]}"
    return None


def candidate_id_for(key: str) -> str:
    """Create the stable candidate identifier used in canonical output."""

    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def choose_candidate_group(profiles: list[SourceProfile]) -> tuple[str | None, list[SourceProfile], list[SourceIssue]]:
    """Pick the largest identity group and report profiles that cannot be merged."""

    groups: dict[str, list[SourceProfile]] = {}
    issues: list[SourceIssue] = []
    for profile in profiles:
        issues.extend(profile.issues)
        key = identity_key(profile)
        if key:
            groups.setdefault(key, []).append(profile)
        else:
            issues.append(SourceIssue(profile.source_id, "unmatched_source: no deterministic identity key"))
    if not groups:
        return None, [], issues
    selected_key = sorted(groups, key=lambda key: (-len(groups[key]), key))[0]
    for key, grouped in groups.items():
        if key != selected_key:
            for profile in grouped:
                issues.append(SourceIssue(profile.source_id, f"unmatched_source: belongs to identity group {key}"))
    return selected_key, groups[selected_key], issues


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z]", "", value.lower())
