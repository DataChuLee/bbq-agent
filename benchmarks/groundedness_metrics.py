from __future__ import annotations

from collections.abc import Iterable, Mapping


def claim_support_summary(verdicts: Iterable[Mapping[str, object]]) -> dict[str, float | int]:
    """근거로 지지되는 사실 주장 비율을 집계한다."""
    items = list(verdicts)
    supported = sum(item.get("verdict") == "supported" for item in items)
    unsupported = sum(item.get("verdict") == "unsupported" for item in items)
    not_applicable = len(items) - supported - unsupported
    factual_claim_count = supported + unsupported
    return {
        "claim_count": len(items),
        "factual_claim_count": factual_claim_count,
        "supported_claim_count": supported,
        "unsupported_claim_count": unsupported,
        "not_applicable_claim_count": not_applicable,
        "claim_support_rate": supported / factual_claim_count
        if factual_claim_count
        else 0.0,
    }
