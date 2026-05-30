"""
final_answer Tool — 최종 응답 포맷팅.

Menu Agent: 검색 결과를 카드 JSON으로 포맷팅.
"""

import json
from typing import List

from langchain_core.tools import tool


# ── Menu Agent용 ─────────────────────────────────────────────────────────────


@tool
def final_answer_menu(items: List[dict]) -> str:
    """메뉴 검색 결과를 카드 JSON 형태로 최종 응답합니다.

    search_menu 결과를 받아 프론트엔드에서 렌더링할 수 있는
    카드 형태의 JSON으로 포맷팅합니다.

    Args:
        items: search_menu에서 반환된 메뉴 항목 리스트.
               각 항목은 name, category, price, description, allergy,
               nutrition, options 필드를 포함합니다.

    Returns:
        카드 JSON 문자열. type="menu_cards"
    """
    cards = []
    for item in items:
        cards.append(
            {
                "name": item.get("name", ""),
                "category": item.get("category", ""),
                "price": item.get("price", 0),
                "description": item.get("description", ""),
                "allergy": item.get("allergy", ""),
                "nutrition": item.get("nutrition", ""),
                "options": item.get("options", ""),
                "imageURL": item.get("imageURL", ""),
                "product_family": item.get("product_family", ""),
                "recommendation_reason": item.get("recommendation_reason", ""),
                "recommendation_score": item.get("recommendation_score", 0),
                "matched_criteria": item.get("matched_criteria", ""),
            }
        )

    return json.dumps(
        {"type": "menu_cards", "items": cards},
        ensure_ascii=False,
    )
