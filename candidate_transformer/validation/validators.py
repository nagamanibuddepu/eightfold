"""Explicit validation at config, canonical, and output stages."""

from __future__ import annotations

import re
from typing import Any

from candidate_transformer.projection.path import read_path

ALLOWED_TYPES = {"string", "string[]", "number", "object", "array", "boolean"}
ALLOWED_ON_MISSING = {"null", "omit", "error"}
CANONICAL_REQUIRED_KEYS = {
    "candidate_id",
    "full_name",
    "emails",
    "phones",
    "location",
    "links",
    "headline",
    "years_experience",
    "skills",
    "experience",
    "education",
    "publications",
    "provenance",
    "overall_confidence",
}


def validate_config(config: dict[str, Any], canonical_shape: dict[str, Any]) -> None:
    """Validate projection configuration before the pipeline emits output."""

    if config.get("on_missing", "null") not in ALLOWED_ON_MISSING:
        raise ValueError("config.on_missing must be one of null, omit, error")
    if not isinstance(config.get("fields"), list):
        raise ValueError("config.fields must be a list")
    for field in config["fields"]:
        if not isinstance(field, dict) or "path" not in field:
            raise ValueError("each config field must be an object with path")
        if field.get("type") not in ALLOWED_TYPES:
            raise ValueError(f"unsupported type for {field['path']}: {field.get('type')}")
        source_path = field.get("from", field["path"])
        root = re.split(r"\.|\[", source_path)[0]
        if root not in canonical_shape:
            raise ValueError(f"unknown canonical field in projection path: {source_path}")


def validate_canonical(candidate: dict[str, Any]) -> None:
    """Validate the canonical model after merge and before projection."""

    missing = CANONICAL_REQUIRED_KEYS - set(candidate)
    if missing:
        raise ValueError(f"canonical candidate missing keys: {sorted(missing)}")
    if not isinstance(candidate["emails"], list) or not isinstance(candidate["phones"], list):
        raise ValueError("canonical emails and phones must be arrays")
    if not isinstance(candidate["provenance"], list):
        raise ValueError("canonical provenance must be an array")
    fields_with_values = _populated_fields(candidate)
    provenance_fields = {item.get("field", "").split(".")[0] for item in candidate["provenance"] if isinstance(item, dict)}
    required_provenance = fields_with_values - {"candidate_id", "overall_confidence", "provenance"}
    if not required_provenance.issubset(provenance_fields):
        missing_prov = sorted(required_provenance - provenance_fields)
        raise ValueError(f"canonical values missing provenance: {missing_prov}")


def validate_projected_output(output: dict[str, Any], config: dict[str, Any] | None = None) -> None:
    """Validate final output against default or configured schema shape."""

    if config is None:
        validate_canonical(output)
        return
    for field in config.get("fields", []):
        path = field["path"]
        value = read_path(output, path)
        if field.get("required") and value is None:
            raise ValueError(f"projected required field is missing: {path}")
        if value is not None and not _matches_type(value, field["type"]):
            raise ValueError(f"projected field {path} expected {field['type']} but got {type(value).__name__}")


def _populated_fields(candidate: dict[str, Any]) -> set[str]:
    fields: set[str] = set()
    for key, value in candidate.items():
        if key == "_issues":
            continue
        if key in {"location", "links"}:
            if isinstance(value, dict) and any(item for item in value.values() if item):
                fields.add(key)
            continue
        if value not in (None, [], {}, 0.0):
            fields.add(key)
    return fields


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "string[]":
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "boolean":
        return isinstance(value, bool)
    return False
