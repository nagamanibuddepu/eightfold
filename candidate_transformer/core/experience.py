"""Experience interval calculations."""

from __future__ import annotations

from datetime import date


def years_from_experience(experience: list[dict[str, str]], run_date: date) -> float | None:
    """Compute non-overlapping years of experience from YYYY-MM intervals."""

    intervals: list[tuple[int, int]] = []
    for item in experience:
        start = _month_index(item.get("start"))
        end = _month_index(item.get("end")) if item.get("end") else run_date.year * 12 + run_date.month
        if start and end and end >= start:
            intervals.append((start, end))
    if not intervals:
        return None
    intervals.sort()
    merged: list[list[int]] = []
    for start, end in intervals:
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    months = sum(end - start + 1 for start, end in merged)
    return round(months / 12, 1)


def _month_index(value: str | None) -> int | None:
    if not value:
        return None
    try:
        year, month = value.split("-")
        return int(year) * 12 + int(month)
    except (ValueError, AttributeError):
        return None
