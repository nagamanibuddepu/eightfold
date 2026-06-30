"""Small canonical-path reader used by projection configs."""

from __future__ import annotations

import re
from typing import Any


def read_path(data: Any, path: str) -> Any:
    """Read paths such as emails[0] and skills[].name without mutating data."""

    current = data
    for token in path.split("."):
        current = _read_token(current, token)
    return current


def _read_token(value: Any, token: str) -> Any:
    array_match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\[\]", token)
    index_match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\[(\d+)\]", token)
    if array_match:
        key = array_match.group(1)
        items = value.get(key, []) if isinstance(value, dict) else []
        return items if isinstance(items, list) else []
    if index_match:
        key, index_text = index_match.groups()
        items = value.get(key, []) if isinstance(value, dict) else []
        index = int(index_text)
        return items[index] if isinstance(items, list) and index < len(items) else None
    if isinstance(value, list):
        return [item.get(token) for item in value if isinstance(item, dict) and token in item]
    if isinstance(value, dict):
        return value.get(token)
    return None
