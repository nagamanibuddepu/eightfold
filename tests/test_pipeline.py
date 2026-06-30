"""End-to-end tests for the candidate transformer."""

from datetime import date

import pytest

from candidate_transformer.core.models import InputPaths
from candidate_transformer.pipeline import run_pipeline
from candidate_transformer.adapters.github_adapter import parse_github_cache


def test_pipeline_merges_sources_and_projects(monkeypatch) -> None:
    """Structured and unstructured sources merge into a valid custom output."""

    monkeypatch.setattr(
        "candidate_transformer.pipeline.parse_github_profile_url",
        lambda url, cache_path: parse_github_cache(url, cache_path),
    )
    output = run_pipeline(
        InputPaths(
            recruiter_csv="sample_data/recruiter_export.csv",
            ats_json="sample_data/ats_candidate.json",
            notes_txt="sample_data/recruiter_notes.txt",
            resume="sample_data/resume.pdf",
            github_url="https://github.com/aaravm",
            github_cache="sample_data/github_api_cache.json",
        ),
        config={
            "fields": [
                {"path": "full_name", "type": "string", "required": True},
                {"path": "primary_email", "from": "emails[0]", "type": "string", "required": True},
                {"path": "skills", "from": "skills[].name", "type": "string[]", "normalize": "canonical"},
            ],
            "include_confidence": True,
            "on_missing": "null",
        },
        run_date=date(2026, 6, 30),
    )
    assert output["full_name"] == "Nagamani Buddepu"
    assert output["primary_email"] == "mbuddepu0827@gmail.com"
    assert "python" in output["skills"]
    assert "react" in output["skills"]
    assert output["overall_confidence"] > 0.5


def test_malformed_source_is_reported_not_fatal() -> None:
    """A malformed structured source is preserved as a run issue."""

    output = run_pipeline(
        InputPaths(
            recruiter_csv="sample_data/malformed_recruiter_export.csv",
            ats_json="sample_data/ats_candidate.json",
        ),
        run_date=date(2026, 6, 30),
    )
    assert output["candidate_id"]
    assert any("malformed CSV" in issue["message"] for issue in output["_issues"])


def test_pipeline_works_when_resume_is_missing(monkeypatch) -> None:
    """The pipeline continues to work when a resume file is missing."""

    monkeypatch.setattr(
        "candidate_transformer.pipeline.parse_github_profile_url",
        lambda url, cache_path: parse_github_cache(url, cache_path),
    )
    output = run_pipeline(
        InputPaths(
            recruiter_csv="sample_data/recruiter_export.csv",
            ats_json="sample_data/ats_candidate.json",
            notes_txt="sample_data/recruiter_notes.txt",
            resume="sample_data/does_not_exist.pdf",
            github_url="https://github.com/aaravm",
            github_cache="sample_data/github_api_cache.json",
        ),
        run_date=date(2026, 6, 30),
    )
    assert output["candidate_id"]
    assert output["full_name"] == "Nagamani Buddepu"


def test_github_never_establishes_identity(monkeypatch) -> None:
    """GitHub is supplemental evidence and cannot create a candidate by itself."""

    monkeypatch.setattr(
        "candidate_transformer.pipeline.parse_github_profile_url",
        lambda url, cache_path: parse_github_cache(url, cache_path),
    )
    with pytest.raises(ValueError, match="no deterministic candidate identity"):
        run_pipeline(
            InputPaths(
                github_url="https://github.com/aaravm",
                github_cache="sample_data/github_api_cache.json",
            ),
            run_date=date(2026, 6, 30),
        )


def test_pipeline_deduplicates_experience_education_and_phones(monkeypatch) -> None:
    """Semantically identical roles and duplicate phone variants collapse to one record."""

    monkeypatch.setattr(
        "candidate_transformer.pipeline.parse_github_profile_url",
        lambda url, cache_path: parse_github_cache(url, cache_path),
    )
    output = run_pipeline(
        InputPaths(
            recruiter_csv="sample_data/recruiter_export.csv",
            ats_json="sample_data/ats_candidate.json",
            notes_txt="sample_data/recruiter_notes.txt",
            resume="sample_data/resume.pdf",
            github_url="https://github.com/aaravm",
            github_cache="sample_data/github_api_cache.json",
        ),
        run_date=date(2026, 6, 30),
    )
    assert output["phones"] == ["+919398172938"]
    assert len(output["education"]) == 1
    assert output["education"][0]["end_year"] == 2027
    assert len(output["experience"]) == 3
    companies = {item["company"] for item in output["experience"]}
    assert companies == {"Infosys SpringBoard", "Campus Labs", "CloudKite"}
    infosys = next(item for item in output["experience"] if item["company"] == "Infosys SpringBoard")
    assert infosys["summary"] == "Built data ingestion jobs and internal dashboards."
    assert infosys["start"] == "2026-02"
    assert infosys["end"] == "2026-04"
