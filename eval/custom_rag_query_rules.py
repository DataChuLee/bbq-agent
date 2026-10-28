from __future__ import annotations

from copy import deepcopy
from typing import Any

from tools.cs_query_rules import preprocess_cs_query  # noqa: F401

RISKY_FILTER_KEYS = ("sauce_style", "product_family")


def _filter_key(filter_part: dict[str, Any]) -> str | None:
    if len(filter_part) != 1:
        return None
    return next(iter(filter_part))


def _compact_filter(parts: list[dict[str, Any]]) -> dict[str, Any]:
    if not parts:
        return {}
    if len(parts) == 1:
        return deepcopy(parts[0])
    return {"$and": deepcopy(parts)}


def build_relaxed_filter_candidates(strict_filter: dict[str, Any]) -> list[dict[str, Any]]:
    """결과가 없을 때 순차적으로 시도할 Chroma 필터 후보를 만든다."""
    if not strict_filter:
        return [{}]

    if "$and" not in strict_filter:
        return [deepcopy(strict_filter), {}]

    parts = list(strict_filter.get("$and") or [])
    candidates = [_compact_filter(parts)]

    current = parts
    for risky_key in RISKY_FILTER_KEYS:
        relaxed = [
            filter_part
            for filter_part in current
            if _filter_key(filter_part) != risky_key
        ]
        if relaxed != current:
            candidates.append(_compact_filter(relaxed))
            current = relaxed

    if candidates[-1] != {}:
        candidates.append({})

    return candidates
