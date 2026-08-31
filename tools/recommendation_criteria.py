"""Recommendation criteria matching and deterministic menu reranking."""

from __future__ import annotations

import copy
import json
import re
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


def _canonical_product_family(value: object) -> str:
    family = str(value or "")
    if family in {"main_chicken", "single_chicken", "combo_chicken"}:
        return "chicken"
    return family


def _canonical_product_type(item: dict[str, Any]) -> str:
    product_type = str(item.get("product_type") or "")
    if product_type:
        return product_type

    family = str(item.get("product_family") or "")
    if family in {"main_chicken", "single_chicken", "chicken"}:
        return "main_menu"
    if family == "combo_chicken":
        return "set_menu"
    if family in {"side", "sauce", "drink"}:
        return family

    category = str(item.get("category") or "")
    if category == "세트메뉴":
        return "set_menu"
    if category in {"후라이드", "양념", "구이", "1인분 메뉴", "반반", "시즈닝", "피자&버거"}:
        return "main_menu"
    if category == "사이드메뉴":
        return "side"
    if category == "소스&시즈닝&무":
        return "sauce"
    if category == "음료":
        return "drink"
    return ""


def _item_text(item: dict[str, Any]) -> str:
    fields = (
        item.get("name", ""),
        item.get("category", ""),
        item.get("texture", ""),
        item.get("primary_texture", ""),
        item.get("spiciness", ""),
        item.get("description", ""),
        _canonical_product_family(item.get("product_family", "")),
        _canonical_product_type(item),
        item.get("cooking_method", ""),
        item.get("sauce_style", ""),
        item.get("option_tags", ""),
    )
    return _normalize(" ".join(str(field) for field in fields))


def _matches_trait(item: dict[str, Any], trait: str) -> bool:
    normalized_trait = _normalize(trait)
    if not normalized_trait:
        return False

    direct_fields = (
        item.get("texture", ""),
        item.get("primary_texture", ""),
        item.get("spiciness", ""),
        item.get("category", ""),
        _canonical_product_family(item.get("product_family", "")),
        _canonical_product_type(item),
        item.get("cooking_method", ""),
        item.get("sauce_style", ""),
    )
    if any(_normalize(field) == normalized_trait for field in direct_fields):
        return True

    return normalized_trait in _item_text(item)


def _matches_profile_filters(item: dict[str, Any], filters: dict[str, Any]) -> bool:
    for field, allowed_values in filters.items():
        if isinstance(allowed_values, str):
            allowed = {_normalize(allowed_values)}
        else:
            allowed = {_normalize(value) for value in allowed_values or []}
        if not allowed:
            continue

        if field == "product_family":
            value = _canonical_product_family(item.get("product_family", ""))
        elif field == "product_type":
            value = _canonical_product_type(item)
        else:
            value = str(item.get(field) or "")

        if _normalize(value) not in allowed:
            return False
    return True


def filter_items_by_recommendation_profile(
    query: str, items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    criteria = detect_recommendation_criteria(query)
    if not criteria:
        return items

    filters = criteria.get("default_filters") or {}
    if not isinstance(filters, dict) or not filters:
        return items

    return [item for item in items if _matches_profile_filters(item, filters)]


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

    if _canonical_product_family(item.get("product_family")) == "chicken" or _canonical_product_type(
        item
    ) in {"main_menu", "set_menu"}:
        score += family_weight

    return score, matched_traits


def _build_reason(criteria: dict[str, Any], matched_traits: list[str]) -> str:
    base_reason = str(criteria.get("reason") or "").strip()
    display_traits = [
        trait
        for trait in matched_traits
        if "_" not in trait and re.search(r"[가-힣]", trait)
    ]
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
