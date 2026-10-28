from eval.custom_rag_metrics import (
    evaluate_rankings,
    hit_at_k,
    keyword_recall,
    precision_at_k,
    reciprocal_rank,
)


def test_precision_at_k_counts_relevant_items_in_top_k() -> None:
    score = precision_at_k(
        retrieved_ids=["a", "b", "c", "d"],
        expected_ids=["a", "c"],
        k=3,
    )

    assert score == 2 / 3


def test_precision_at_k_divides_by_k_and_ignores_duplicate_hits() -> None:
    score = precision_at_k(
        retrieved_ids=["a", "a"],
        expected_ids=["a", "b"],
        k=5,
    )

    assert score == 1 / 5


def test_hit_at_k_only_checks_the_requested_window() -> None:
    retrieved_ids = ["x", "answer"]
    expected_ids = ["answer"]

    assert hit_at_k(retrieved_ids, expected_ids, k=1) == 0.0
    assert hit_at_k(retrieved_ids, expected_ids, k=2) == 1.0


def test_reciprocal_rank_uses_first_relevant_position() -> None:
    score = reciprocal_rank(
        retrieved_ids=["x", "y", "answer"],
        expected_ids=["answer"],
    )

    assert score == 1 / 3


def test_keyword_recall_counts_expected_terms_found_in_texts() -> None:
    score = keyword_recall(
        retrieved_texts=["고객에게 먼저 사과하고 주문 매장을 확인한다."],
        expected_keywords=["사과", "주문 매장", "환불"],
    )

    assert score == 2 / 3


def test_evaluate_rankings_returns_detail_rows_and_averaged_summary() -> None:
    cases = [
        {
            "id": "case-1",
            "query": "첫 번째 질문",
            "expected_ids": ["a"],
            "case_type": "exact",
        },
        {
            "id": "case-2",
            "query": "두 번째 질문",
            "expected_ids": ["z"],
            "case_type": "miss",
        },
    ]
    predictions = {
        "case-1": ["a", "b", "c"],
        "case-2": ["x", "y", "z"],
    }

    detail_rows, summary = evaluate_rankings(
        cases=cases,
        predictions=predictions,
        k_values=(1, 3),
    )

    assert detail_rows[0]["precision@1"] == 1.0
    assert detail_rows[1]["hit@1"] == 0.0
    assert detail_rows[1]["mrr"] == 1 / 3
    assert summary["precision@1"] == 0.5
    assert summary["hit@3"] == 1.0
    assert summary["mrr"] == (1.0 + 1 / 3) / 2
