"""Shared data models used between pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceIssue:
    """A non-fatal issue found while reading or transforming one source."""

    source_id: str
    message: str


@dataclass(frozen=True)
class SourceProfile:
    """Candidate facts extracted from one input before or after normalization."""

    source_id: str
    source_type: str
    reliability: float
    method: str
    fields: dict[str, Any] = field(default_factory=dict)
    issues: tuple[SourceIssue, ...] = ()


@dataclass(frozen=True)
class MergeResult:
    """The merged canonical candidate and source issues produced by a run."""

    canonical: dict[str, Any]
    issues: tuple[SourceIssue, ...]


@dataclass(frozen=True)
class InputPaths:
    """CLI input paths grouped by adapter type."""

    recruiter_csv: str | None = None
    ats_json: str | None = None
    notes_txt: str | None = None
    resume: str | None = None
    github_url: str | None = None
    github_cache: str | None = None
    # sample_ats: str | None = None
