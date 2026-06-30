"""End-to-end candidate transformation pipeline."""

from __future__ import annotations

from datetime import date
from typing import Any

from candidate_transformer.adapters.ats_json_adapter import parse_ats_json
from candidate_transformer.adapters.csv_adapter import parse_recruiter_csv
from candidate_transformer.adapters.github_adapter import parse_github_profile_url
from candidate_transformer.adapters.notes_adapter import parse_recruiter_notes
from candidate_transformer.adapters.resume_adapter import parse_resume
from candidate_transformer.core.identity import choose_candidate_group
from candidate_transformer.core.merge import CANONICAL_TEMPLATE, merge_profiles
from candidate_transformer.core.models import InputPaths, SourceIssue, SourceProfile
from candidate_transformer.core.normalize import normalize_source_profile
from candidate_transformer.projection.projector import project_candidate
from candidate_transformer.validation.validators import validate_canonical, validate_config, validate_projected_output


def run_pipeline(inputs: InputPaths, config: dict[str, Any] | None = None, default_region: str = "US", run_date: date | None = None) -> dict[str, Any]:
    """Run detect, parse, extract, normalize, identity, merge, confidence, provenance, projection, validation, and output."""

    if config is not None:
        validate_config(config, CANONICAL_TEMPLATE)
    raw_profiles = _detect_parse_extract(inputs)
    normalized_profiles = [normalize_source_profile(profile, default_region) for profile in raw_profiles]
    identity_profiles = [profile for profile in normalized_profiles if profile.source_type != "github"]
    supplemental_profiles = [profile for profile in normalized_profiles if profile.source_type == "github"]
    identity_key, matched_profiles, identity_issues = choose_candidate_group(identity_profiles)
    if not identity_key:
        raise ValueError("no deterministic candidate identity could be resolved from provided sources")
    merged = merge_profiles(identity_key, [*matched_profiles, *supplemental_profiles], run_date or date.today())
    canonical = merged.canonical
    canonical["_issues"] = _dedupe_issues((*identity_issues, *merged.issues))
    validate_canonical(canonical)
    output = project_candidate(canonical, config)
    validate_projected_output(output, config)
    return output


def _detect_parse_extract(inputs: InputPaths) -> list[SourceProfile]:
    profiles: list[SourceProfile] = []
    if inputs.recruiter_csv:
        profiles.extend(parse_recruiter_csv(inputs.recruiter_csv))
    if inputs.ats_json:
        profiles.extend(parse_ats_json(inputs.ats_json))
    if inputs.notes_txt:
        profiles.extend(parse_recruiter_notes(inputs.notes_txt))
    if inputs.resume:
        profiles.extend(parse_resume(inputs.resume))
    if inputs.github_url:
        profiles.extend(parse_github_profile_url(inputs.github_url, inputs.github_cache))
    return profiles


def _issue_to_dict(issue: SourceIssue) -> dict[str, str]:
    return {"source": issue.source_id, "message": issue.message}


def _dedupe_issues(issues: tuple[SourceIssue, ...]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for issue in issues:
        key = (issue.source_id, issue.message)
        if key not in seen:
            seen.add(key)
            result.append(_issue_to_dict(issue))
    return result
