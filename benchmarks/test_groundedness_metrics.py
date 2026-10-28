from benchmarks.groundedness_metrics import claim_support_summary


def test_claim_support_summary_excludes_non_factual_items() -> None:
    summary = claim_support_summary(
        [
            {"verdict": "supported"},
            {"verdict": "unsupported"},
            {"verdict": "not_applicable"},
        ]
    )

    assert summary == {
        "claim_count": 3,
        "factual_claim_count": 2,
        "supported_claim_count": 1,
        "unsupported_claim_count": 1,
        "not_applicable_claim_count": 1,
        "claim_support_rate": 0.5,
    }


def test_claim_support_summary_returns_zero_when_no_factual_claim_exists() -> None:
    summary = claim_support_summary([{"verdict": "not_applicable"}])

    assert summary["claim_support_rate"] == 0.0
    assert summary["factual_claim_count"] == 0
