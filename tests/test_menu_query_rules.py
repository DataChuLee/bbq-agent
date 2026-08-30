from tools.menu_query_rules import (
    build_relaxed_filter_candidates,
    extract_rule_based_filters,
)


def test_extract_rule_based_filters_builds_menu_metadata_filter() -> None:
    filters = extract_rule_based_filters("2만원 이하 매운 바삭한 치킨 추천해줘")

    assert filters == {
        "$and": [
            {"price": {"$lte": 20000}},
            {"spiciness": {"$eq": "매움"}},
            {"primary_texture": {"$eq": "바삭함"}},
            {"product_family": {"$eq": "chicken"}},
        ]
    }


def test_extract_rule_based_filters_handles_price_above_terms() -> None:
    filters = extract_rule_based_filters("2만원 이상 구운 치킨 찾아줘")

    assert filters == {
        "$and": [
            {"price": {"$gte": 20000}},
            {"product_family": {"$eq": "chicken"}},
            {"cooking_method": {"$eq": "grilled"}},
        ]
    }


def test_build_relaxed_filter_candidates_drops_risky_filters_in_order() -> None:
    strict_filter = {
        "$and": [
            {"spiciness": {"$eq": "매움"}},
            {"product_family": {"$eq": "chicken"}},
            {"sauce_style": {"$eq": "spicy_sauce"}},
        ]
    }

    assert build_relaxed_filter_candidates(strict_filter) == [
        {
            "$and": [
                {"spiciness": {"$eq": "매움"}},
                {"product_family": {"$eq": "chicken"}},
                {"sauce_style": {"$eq": "spicy_sauce"}},
            ]
        },
        {
            "$and": [
                {"spiciness": {"$eq": "매움"}},
                {"product_family": {"$eq": "chicken"}},
            ]
        },
        {"spiciness": {"$eq": "매움"}},
        {},
    ]
