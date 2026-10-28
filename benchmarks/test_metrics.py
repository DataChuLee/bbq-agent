from benchmarks.metrics import (
    duplicate_card_rate,
    evaluate_menu_constraints,
    menu_item_matches_constraints,
    percentile,
)


def test_menu_item_matches_price_and_allowed_family() -> None:
    item = {"price": 1000, "product_family": "sauce"}

    assert menu_item_matches_constraints(
        item,
        {"max_price": 1000, "product_family": ["sauce", "seasoning"]},
    )


def test_menu_item_rejects_unmatched_constraint() -> None:
    assert not menu_item_matches_constraints(
        {"price": 3000, "product_family": "drink"},
        {"max_price": 2500, "product_family": "drink"},
    )


def test_constraint_evaluation_reports_pass_and_valid_item_rate() -> None:
    cases = [
        {
            "id": "case-1",
            "query": "치킨",
            "constraints": {"product_family": "chicken", "max_price": 20000},
        }
    ]
    predictions = {
        "case-1": [
            {"name": "비싼 치킨", "product_family": "chicken", "price": 21000},
            {"name": "조건 충족", "product_family": "chicken", "price": 19000},
            {"name": "음료", "product_family": "drink", "price": 1000},
        ]
    }

    rows, summary = evaluate_menu_constraints(cases, predictions, k=3)

    assert rows[0]["constraint_pass@k"] == 1.0
    assert rows[0]["valid_item_rate@k"] == 1 / 3
    assert summary["constraint_pass@k"] == 1.0


def test_duplicate_card_rate_counts_only_previously_shown_names() -> None:
    rate = duplicate_card_rate(
        ["A", "B"],
        [{"name": "B"}, {"name": "C"}, {"name": "D"}],
    )

    assert rate == 1 / 3


def test_percentile_uses_linear_interpolation() -> None:
    assert percentile([10, 20, 30, 40], 0.5) == 25.0
