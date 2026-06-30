"""Tests for explicit validation failure paths."""

import pytest

from candidate_transformer.core.merge import CANONICAL_TEMPLATE
from candidate_transformer.validation.validators import validate_config, validate_projected_output


def test_invalid_projection_path_is_rejected() -> None:
    """Config validation catches unknown canonical source paths before a run."""

    with pytest.raises(ValueError, match="unknown canonical field"):
        validate_config(
            {
                "fields": [
                    {
                        "path": "primary_email",
                        "from": "contact.email",
                        "type": "string",
                    }
                ],
                "on_missing": "null",
            },
            CANONICAL_TEMPLATE,
        )


def test_projected_output_type_mismatch_is_rejected() -> None:
    """Output validation catches fields that do not match config-declared types."""

    with pytest.raises(ValueError, match="expected string\\[\\]"):
        validate_projected_output(
            {"skills": "python"},
            {
                "fields": [
                    {
                        "path": "skills",
                        "type": "string[]",
                    }
                ],
                "on_missing": "null",
            },
        )
