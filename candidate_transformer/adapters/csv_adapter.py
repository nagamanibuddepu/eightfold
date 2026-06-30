"""Recruiter CSV adapter."""

from __future__ import annotations

import csv

from candidate_transformer.core.constants import SOURCE_RELIABILITY
from candidate_transformer.core.models import SourceIssue, SourceProfile


EXPECTED_COLUMNS = {"name", "email", "phone", "current_company", "title"}


def parse_recruiter_csv(path: str) -> list[SourceProfile]:
    """Parse recruiter CSV rows into source profiles without normalizing values."""

    source_id = f"recruiter_csv:{path}"
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not EXPECTED_COLUMNS.issubset(set(reader.fieldnames)):
                missing = sorted(EXPECTED_COLUMNS - set(reader.fieldnames or []))
                return [_error_profile(source_id, f"malformed CSV; missing columns: {missing}")]
            profiles: list[SourceProfile] = []
            for index, row in enumerate(reader, start=1):
                profiles.append(
                    SourceProfile(
                        source_id=f"{source_id}#row{index}",
                        source_type="recruiter_csv",
                        reliability=SOURCE_RELIABILITY["recruiter_csv"],
                        method="recruiter_csv_row",
                        fields={
                            "full_name": row.get("name"),
                            "emails": [row.get("email")] if row.get("email") else [],
                            "phones": [row.get("phone")] if row.get("phone") else [],
                            "headline": row.get("title"),
                            "experience": [
                                {
                                    "company": row.get("current_company"),
                                    "title": row.get("title"),
                                    "start": None,
                                    "end": None,
                                    "summary": "Current role from recruiter export",
                                }
                            ]
                            if row.get("current_company") or row.get("title")
                            else [],
                        },
                    )
                )
            return profiles
    except OSError as exc:
        return [_error_profile(source_id, f"could not read CSV: {exc}")]


def _error_profile(source_id: str, message: str) -> SourceProfile:
    return SourceProfile(source_id, "recruiter_csv", SOURCE_RELIABILITY["recruiter_csv"], "read_error", {}, (SourceIssue(source_id, message),))
