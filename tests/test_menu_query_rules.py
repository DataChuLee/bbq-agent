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


def test_extract_rule_based_filters_reads_negated_conditions() -> None:
    assert extract_rule_based_filters("매운 거 못 먹는 사람도 먹을 수 있는 치킨") == {
        "$and": [
            {"spiciness": {"$eq": "순함"}},
            {"product_family": {"$eq": "chicken"}},
        ]
    }
    assert extract_rule_based_filters("양념 말고 후라이드로 추천해줘") == {
        "category": {"$eq": "후라이드"}
    }


def test_extract_excluded_terms_reads_allergens_and_alternatives() -> None:
    from tools.menu_query_rules import extract_excluded_terms

    assert extract_excluded_terms("새우 알레르기 있는데 먹을 수 있는 사이드") == ["새우"]
    assert extract_excluded_terms("우유 안 들어간 치킨") == ["우유"]
    assert extract_excluded_terms("콜라 말고 다른 음료") == ["콜라"]
    assert extract_excluded_terms("계란 빼고") == ["계란", "알류"]
    assert extract_excluded_terms("매운 치킨 추천해줘") == []


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
