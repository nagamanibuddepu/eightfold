"""Tests for deterministic source-local normalization."""

from candidate_transformer.core.normalize import canonical_skill, normalize_country, normalize_email, normalize_phone


def test_normalize_email_and_phone() -> None:
    """Emails are lowercased and local US phones become E.164."""

    assert normalize_email(" AARAV.MEHTA@Example.com ") == "aarav.mehta@example.com"
    assert normalize_phone("(415) 555-0198", "US") == "+14155550198"


def test_country_and_skill_aliases() -> None:
    """Country and skill aliases are deterministic and conservative."""

    assert normalize_country("United States") == "US"
    assert canonical_skill("ReactJS") == ("react", "skill_alias")
    assert canonical_skill("GraphQL") == ("graphql", "skill_passthrough")
