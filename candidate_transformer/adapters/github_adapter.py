"""GitHub public REST API adapter with deterministic cache fallback."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from candidate_transformer.core.constants import SOURCE_RELIABILITY
from candidate_transformer.core.models import SourceIssue, SourceProfile

GITHUB_API = "https://api.github.com"


def parse_github_profile_url(profile_url: str, cache_path: str | None = None, timeout_seconds: int = 2) -> list[SourceProfile]:
    """Fetch a GitHub profile via the public REST API and infer candidate evidence.

    A cache path is optional and only used when the public API is unavailable,
    rate-limited, or the profile URL is intentionally fictitious for tests/demos.
    """

    username = _username_from_url(profile_url)
    source_id = f"github:{profile_url}"
    if not username:
        return [_error_profile(source_id, "GitHub URL must look like https://github.com/<username>")]

    try:
        user = _fetch_json(f"{GITHUB_API}/users/{username}", timeout_seconds)
        repos = _fetch_json(f"{GITHUB_API}/users/{username}/repos?per_page=100&sort=updated", timeout_seconds)
        return [_profile_from_api(source_id, user, repos, "github_live_api")]
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
        if cache_path:
            cached = parse_github_cache(profile_url, cache_path)
            return _with_issue(cached, SourceIssue(source_id, f"GitHub live API unavailable; used cache fallback: {exc}"))
        return [_error_profile(source_id, f"GitHub live API unavailable and no cache was provided: {exc}")]


def parse_github_cache(profile_url: str, cache_path: str) -> list[SourceProfile]:
    """Parse a cached GitHub API-shaped profile for deterministic demos/tests."""

    source_id = f"github:{profile_url}"
    try:
        with open(cache_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return [_error_profile(source_id, f"could not parse GitHub cache: {exc}")]
    if not isinstance(data, dict):
        return [_error_profile(source_id, "GitHub cache root must be an object")]

    user = data.get("user", data)
    repos = data.get("repos", data.get("repositories", []))
    if not isinstance(user, dict):
        return [_error_profile(source_id, "GitHub cache user must be an object")]
    if not isinstance(repos, list):
        repos = []
    return [_profile_from_api(source_id, user, repos, "github_cached_api")]


def _username_from_url(profile_url: str) -> str | None:
    match = re.fullmatch(r"https?://(?:www\.)?github\.com/([A-Za-z0-9-]+)/*", profile_url.strip())
    if not match:
        return None
    return match.group(1)


def _fetch_json(url: str, timeout_seconds: int) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "eightfold-candidate-transformer"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        if response.status >= 400:
            raise ValueError(f"GitHub API returned HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def _profile_from_api(source_id: str, user: dict[str, Any], repos: list[Any], method: str) -> SourceProfile:
    return SourceProfile(
        source_id=source_id,
        source_type="github",
        reliability=SOURCE_RELIABILITY["github"],
        method=method,
        fields={
            "full_name": user.get("name"),
            "emails": [],
            "links": {
                "github": user.get("html_url"),
                "portfolio": user.get("blog"),
            },
            "headline": user.get("bio"),
            "skills": _infer_languages(repos),
        },
    )


def _infer_languages(repos: list[Any]) -> list[str]:
    languages: list[str] = []
    for repo in repos:
        if isinstance(repo, dict):
            language = repo.get("language")
            if language and language not in languages:
                languages.append(language)
    return languages


def _with_issue(profiles: list[SourceProfile], issue: SourceIssue) -> list[SourceProfile]:
    return [
        SourceProfile(profile.source_id, profile.source_type, profile.reliability, profile.method, profile.fields, (*profile.issues, issue))
        for profile in profiles
    ]


def _error_profile(source_id: str, message: str) -> SourceProfile:
    return SourceProfile(source_id, "github", SOURCE_RELIABILITY["github"], "read_error", {}, (SourceIssue(source_id, message),))
