"""Runtime projection from canonical candidate to requested output shape."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from candidate_transformer.core.normalize import canonical_skill, normalize_phone
from candidate_transformer.projection.path import read_path


def project_candidate(canonical: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return either the default canonical output or a configured projection."""

    if config is None:
        return deepcopy(canonical)

    output: dict[str, Any] = {}
    on_missing = config.get("on_missing", "null")
    for field in config.get("fields", []):
        output_path = field["path"]
        source_path = field.get("from", output_path)
        value = read_path(canonical, source_path)
        value = _apply_projection_normalization(value, field.get("normalize"))
        if _is_missing(value):
            if field.get("required") or on_missing == "error":
                raise ValueError(f"missing required projected field: {output_path}")
            if on_missing == "omit":
                continue
            value = None
        output[output_path] = value

    if config.get("include_confidence", False):
        output["overall_confidence"] = canonical.get("overall_confidence")
    if config.get("include_provenance", False):
        output["provenance"] = deepcopy(canonical.get("provenance", []))
    return output


def _apply_projection_normalization(value: Any, normalization: str | None) -> Any:
    if normalization is None or value is None:
        return value
    if normalization.upper() == "E164":
        if isinstance(value, list):
            return [normalize_phone(item) for item in value if normalize_phone(item)]
        return normalize_phone(str(value))
    if normalization.lower() == "canonical":
        if isinstance(value, list):
            return [canonical_skill(str(item))[0] for item in value if canonical_skill(str(item))[0]]
        return canonical_skill(str(value))[0]
    raise ValueError(f"unsupported projection normalization: {normalization}")


def _is_missing(value: Any) -> bool:
    return value is None or value == [] or value == {}
