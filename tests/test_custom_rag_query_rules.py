from eval.custom_rag_query_rules import (
    build_relaxed_filter_candidates,
    preprocess_cs_query,
)


def test_preprocess_cs_query_keeps_gift_certificate_distinct_from_gifticon() -> None:
    query = "문화상품권을 안 받아준다고 하는데 뭐라고 안내해야 해?"

    assert preprocess_cs_query(query) == query


def test_preprocess_cs_query_corrects_gifticon_typo() -> None:
    query = "기프티곤 오류가 나서 주문이 안 된대"

    assert preprocess_cs_query(query) == "기프티콘 오류가 나서 주문이 안 된대"


def test_build_relaxed_filter_candidates_drops_risky_filters_first() -> None:
    strict_filter = {
        "$and": [
            {"spiciness": {"$eq": "매움"}},
            {"product_family": {"$eq": "chicken"}},
            {"sauce_style": {"$eq": "sauced"}},
        ]
    }

    candidates = build_relaxed_filter_candidates(strict_filter)

    assert candidates == [
        {
            "$and": [
                {"spiciness": {"$eq": "매움"}},
                {"product_family": {"$eq": "chicken"}},
                {"sauce_style": {"$eq": "sauced"}},
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


def test_build_relaxed_filter_candidates_handles_single_filter() -> None:
    assert build_relaxed_filter_candidates({"category": {"$eq": "신메뉴"}}) == [
        {"category": {"$eq": "신메뉴"}},
        {},
    ]
