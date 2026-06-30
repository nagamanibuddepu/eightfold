"""Tests for read-only custom projection behavior."""

from copy import deepcopy

from candidate_transformer.projection.projector import project_candidate


def test_projection_does_not_mutate_canonical() -> None:
    """Projection reshapes output while leaving canonical data unchanged."""

    canonical = {
        "emails": ["a@example.com"],
        "phones": ["+14155550198"],
        "skills": [{"name": "python"}],
        "overall_confidence": 0.9,
    }
    before = deepcopy(canonical)
    output = project_candidate(
        canonical,
        {
            "fields": [{"path": "primary_email", "from": "emails[0]", "type": "string", "required": True}],
            "include_confidence": True,
            "on_missing": "null",
        },
    )
    assert output == {"primary_email": "a@example.com", "overall_confidence": 0.9}
    assert canonical == before
