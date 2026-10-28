from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any


def percentile(values: Sequence[float], ratio: float) -> float:
    """정렬된 관측값에서 선형 보간 방식으로 백분위수를 계산한다."""
    if not values:
        return 0.0
    if not 0 <= ratio <= 1:
        raise ValueError("ratio는 0과 1 사이여야 합니다.")

    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * ratio
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _normalized_values(value: object) -> set[str]:
    if isinstance(value, str):
        values: Iterable[object] = [value]
    elif isinstance(value, Iterable):
        values = value
    else:
        values = [value]
    return {str(item).strip().casefold() for item in values if str(item).strip()}


def menu_item_matches_constraints(
    item: Mapping[str, Any],
    constraints: Mapping[str, Any],
) -> bool:
    """메뉴 카드가 평가 케이스의 하드 조건을 모두 만족하는지 판정한다."""
    max_price = constraints.get("max_price")
    if max_price is not None and int(item.get("price") or 0) > int(max_price):
        return False

    min_price = constraints.get("min_price")
    if min_price is not None and int(item.get("price") or 0) < int(min_price):
        return False

    for field, expected in constraints.items():
        if field in {"max_price", "min_price"}:
            continue
        allowed = _normalized_values(expected)
        actual = str(item.get(field) or "").strip().casefold()
        if allowed and actual not in allowed:
            return False
    return True


def evaluate_menu_constraints(
    cases: Sequence[Mapping[str, Any]],
    predictions: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    k: int = 3,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """조건형 메뉴 검색의 상위 k개 결과를 평가한다."""
    if k <= 0:
        raise ValueError("k는 1 이상이어야 합니다.")

    rows: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case["id"])
        items = list(predictions.get(case_id, []))[:k]
        matched = [
            item
            for item in items
            if menu_item_matches_constraints(item, case.get("constraints", {}))
        ]
        rows.append(
            {
                "id": case_id,
                "query": case.get("query", ""),
                "constraints": dict(case.get("constraints", {})),
                "returned_names": [str(item.get("name") or "") for item in items],
                "constraint_pass@k": 1.0 if matched else 0.0,
                "valid_item_rate@k": len(matched) / len(items) if items else 0.0,
            }
        )

    total = len(rows)
    return rows, {
        "constraint_pass@k": (
            sum(row["constraint_pass@k"] for row in rows) / total if total else 0.0
        ),
        "valid_item_rate@k": (
            sum(row["valid_item_rate@k"] for row in rows) / total if total else 0.0
        ),
        "case_count": float(total),
    }


def duplicate_card_rate(
    shown_names: Iterable[object],
    returned_items: Iterable[Mapping[str, Any]],
) -> float:
    """후속 응답 카드 중 이전에 노출된 메뉴가 차지하는 비율을 계산한다."""
    shown = {str(name).strip() for name in shown_names if str(name).strip()}
    returned = list(returned_items)
    if not returned:
        return 0.0
    duplicates = sum(
        1 for item in returned if str(item.get("name") or "").strip() in shown
    )
    return duplicates / len(returned)
