"""Recommendation criteria matching and deterministic menu reranking."""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


CRITERIA_PATH = Path(__file__).parent.parent / "Data" / "recommendation_criteria.json"
DEFAULT_TOP_K = 5


@lru_cache(maxsize=1)
def load_recommendation_criteria() -> list[dict[str, Any]]:
    with open(CRITERIA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return [record for record in data if isinstance(record, dict)]


def _normalize(value: object) -> str:
    return str(value or "").replace(" ", "").lower()


def detect_recommendation_criteria(query: str) -> dict[str, Any] | None:
    normalized_query = _normalize(query)
    if not normalized_query:
        return None

    for criteria in load_recommendation_criteria():
        expressions = criteria.get("user_expressions") or []
        for expression in expressions:
            if _normalize(expression) in normalized_query:
                return copy.deepcopy(criteria)

    return None


def build_criteria_retrieval_query(query: str) -> str:
    criteria = detect_recommendation_criteria(query)
    if not criteria:
        return query

    retrieval_query = str(criteria.get("retrieval_query") or "").strip()
    return retrieval_query or query


def _item_text(item: dict[str, Any]) -> str:
    fields = (
        item.get("name", ""),
        item.get("category", ""),
        item.get("texture", ""),
        item.get("spiciness", ""),
        item.get("description", ""),
        item.get("product_family", ""),
    )
    return _normalize(" ".join(str(field) for field in fields))


def _matches_trait(item: dict[str, Any], trait: str) -> bool:
    normalized_trait = _normalize(trait)
    if not normalized_trait:
        return False

    direct_fields = (
        item.get("texture", ""),
        item.get("spiciness", ""),
        item.get("category", ""),
        item.get("product_family", ""),
    )
    if any(_normalize(field) == normalized_trait for field in direct_fields):
        return True

    return normalized_trait in _item_text(item)


def _score_item(item: dict[str, Any], criteria: dict[str, Any]) -> tuple[int, list[str]]:
    weights = criteria.get("weights") or {}
    preferred_weight = int(weights.get("preferred", 2))
    avoid_weight = int(weights.get("avoid", -2))
    family_weight = int(weights.get("family", 1))

    score = 0
    matched_traits: list[str] = []

    for trait in criteria.get("preferred_traits") or []:
        if _matches_trait(item, str(trait)):
            score += preferred_weight
            matched_traits.append(str(trait))

    for trait in criteria.get("avoid_traits") or []:
        if _matches_trait(item, str(trait)):
            score += avoid_weight

    if str(item.get("product_family") or "") in {
        "main_chicken",
        "single_chicken",
        "combo_chicken",
    }:
        score += family_weight

    return score, matched_traits


def _build_reason(criteria: dict[str, Any], matched_traits: list[str]) -> str:
    base_reason = str(criteria.get("reason") or "").strip()
    display_traits = [trait for trait in matched_traits if "_" not in trait]
    if not display_traits:
        return base_reason

    unique_traits = list(dict.fromkeys(display_traits))
    trait_text = ", ".join(unique_traits[:3])
    if not base_reason:
        return f"추천 기준상 {trait_text} 특성이 요청과 잘 맞습니다."
    return f"{base_reason} 이 메뉴는 {trait_text} 특성이 있어 요청과 잘 맞습니다."


def rerank_menu_items(query: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    criteria = detect_recommendation_criteria(query)
    if not criteria:
        return items

    scored_items = []
    for index, item in enumerate(items):
        score, matched_traits = _score_item(item, criteria)
        ranked_item = dict(item)
        ranked_item["recommendation_score"] = score
        ranked_item["matched_criteria"] = str(criteria.get("intent") or "")
        ranked_item["recommendation_reason"] = _build_reason(criteria, matched_traits)
        scored_items.append((score, index, ranked_item))

    scored_items.sort(key=lambda entry: (-entry[0], entry[1]))
    return [item for _, _, item in scored_items[:DEFAULT_TOP_K]]
