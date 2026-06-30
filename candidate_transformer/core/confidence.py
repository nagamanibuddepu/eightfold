"""Confidence scoring for merged canonical values."""

from __future__ import annotations

from statistics import mean
from typing import Any

from candidate_transformer.core.constants import AGREEMENT_BONUS, CONFLICT_PENALTY


def scalar_confidence(values: list[tuple[Any, float]], conflict: bool = False) -> float:
    """Score a scalar field from source reliabilities and conflict status."""

    if not values:
        return 0.0
    distinct = {str(value).lower() for value, _ in values if value is not None}
    base = max(reliability for _, reliability in values)
    agreement = AGREEMENT_BONUS * (1 - (len(distinct) - 1) / max(len(values), 1)) if len(values) > 1 else 0
    penalty = CONFLICT_PENALTY if conflict else 0
    return _clamp(base + agreement - penalty)


def array_item_confidence(reliabilities: list[float]) -> float:
    """Score a merged array item from all sources that supplied it."""

    if not reliabilities:
        return 0.0
    bonus = AGREEMENT_BONUS * (len(reliabilities) - 1) / max(len(reliabilities), 1)
    return _clamp(mean(reliabilities) + bonus)


def overall_confidence(field_confidences: dict[str, float]) -> float:
    """Return the average confidence for populated canonical fields."""

    values = [value for value in field_confidences.values() if value > 0]
    return round(mean(values), 3) if values else 0.0


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)
