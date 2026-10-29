from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


def _require_positive_k(k: int) -> None:
    if k <= 0:
        raise ValueError("k는 1 이상이어야 합니다.")


def _normalize_id(value: object) -> str:
    return str(value).strip().casefold()


def _normalize_ids(values: Iterable[object]) -> list[str]:
    return [normalized for value in values if (normalized := _normalize_id(value))]


def precision_at_k(
    retrieved_ids: Sequence[object],
    expected_ids: Iterable[object],
    k: int,
) -> float:
    """상위 k개 결과 중 정답 ID가 차지하는 비율을 계산한다."""
    _require_positive_k(k)
    expected = set(_normalize_ids(expected_ids))
    if not expected:
        return 0.0

    hits = 0
    seen: set[str] = set()
    for result_id in _normalize_ids(retrieved_ids[:k]):
        if result_id in seen:
            continue
        seen.add(result_id)
        if result_id in expected:
            hits += 1

    return hits / k


def hit_at_k(
    retrieved_ids: Sequence[object],
    expected_ids: Iterable[object],
    k: int,
) -> float:
    """상위 k개 결과 안에 정답 ID가 하나라도 있으면 1.0을 반환한다."""
    _require_positive_k(k)
    expected = set(_normalize_ids(expected_ids))
    if not expected:
        return 0.0

    retrieved = set(_normalize_ids(retrieved_ids[:k]))
    return 1.0 if retrieved & expected else 0.0


def reciprocal_rank(
    retrieved_ids: Sequence[object],
    expected_ids: Iterable[object],
) -> float:
    """첫 번째 정답 결과의 역순위를 계산한다."""
    expected = set(_normalize_ids(expected_ids))
    if not expected:
        return 0.0

    seen: set[str] = set()
    for index, result_id in enumerate(_normalize_ids(retrieved_ids), start=1):
        if result_id in seen:
            continue
        seen.add(result_id)
        if result_id in expected:
            return 1 / index
    return 0.0


def ndcg_at_k(
    retrieved_ids: Sequence[object],
    grades: Mapping[object, int],
    k: int,
) -> float:
    """등급 라벨로 상위 k개의 순위 품질을 0~1로 계산한다. 라벨에 없는 결과는 0점이다."""
    _require_positive_k(k)
    graded = {_normalize_id(key): value for key, value in grades.items()}
    ideal = sorted(graded.values(), reverse=True)[:k]
    ideal_dcg = sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    if not ideal_dcg:
        return 0.0

    seen: set[str] = set()
    dcg = 0.0
    for index, result_id in enumerate(_normalize_ids(retrieved_ids[:k])):
        if result_id in seen:
            continue
        seen.add(result_id)
        dcg += (2 ** graded.get(result_id, 0) - 1) / math.log2(index + 2)
    return dcg / ideal_dcg


def keyword_recall(
    retrieved_texts: Sequence[object],
    expected_keywords: Iterable[object],
) -> float:
    """검색된 문서 텍스트에서 기대 키워드가 얼마나 발견되는지 계산한다."""
    keywords = _normalize_ids(expected_keywords)
    if not keywords:
        return 0.0

    joined_text = "\n".join(str(text) for text in retrieved_texts).casefold()
    hits = sum(1 for keyword in keywords if keyword in joined_text)
    return hits / len(keywords)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def evaluate_rankings(
    cases: Sequence[Mapping[str, Any]],
    predictions: Mapping[str, Sequence[object]],
    k_values: Sequence[int] = (1, 3, 5),
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """골든셋과 검색 결과 ID 목록으로 상세 행과 평균 요약을 만든다."""
    if not k_values:
        raise ValueError("k_values는 비어 있을 수 없습니다.")
    for k in k_values:
        _require_positive_k(k)

    detail_rows: list[dict[str, Any]] = []
    metric_names = [f"precision@{k}" for k in k_values]
    metric_names += [f"hit@{k}" for k in k_values]
    metric_names.append("mrr")

    for case in cases:
        case_id = str(case["id"])
        expected_ids = case.get("expected_ids", [])
        retrieved_ids = list(predictions.get(case_id, []))
        row: dict[str, Any] = {
            "id": case_id,
            "query": case.get("query", ""),
            "case_type": case.get("case_type", ""),
            "expected_ids": list(expected_ids),
            "retrieved_ids": retrieved_ids,
        }

        for k in k_values:
            row[f"precision@{k}"] = precision_at_k(retrieved_ids, expected_ids, k)
            row[f"hit@{k}"] = hit_at_k(retrieved_ids, expected_ids, k)
        row["mrr"] = reciprocal_rank(retrieved_ids, expected_ids)
        detail_rows.append(row)

    summary = {
        metric: _mean([float(row[metric]) for row in detail_rows])
        for metric in metric_names
    }
    return detail_rows, summary
