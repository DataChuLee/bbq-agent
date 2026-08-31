"""Menu response formatting helpers."""

from __future__ import annotations


MENU_CARD_FIELDS = (
    ("name", ""),
    ("category", ""),
    ("price", 0),
    ("description", ""),
    ("allergy", ""),
    ("texture", ""),
    ("spiciness", ""),
    ("nutrition", ""),
    ("options", ""),
    ("imageURL", ""),
    ("product_type", ""),
    ("product_family", ""),
    ("primary_texture", ""),
    ("cooking_method", ""),
    ("sauce_style", ""),
    ("option_tags", ""),
    ("recommendation_reason", ""),
    ("recommendation_score", 0),
    ("matched_criteria", ""),
)


def format_menu_cards(items: list[dict]) -> dict:
    """Format retrieved menu items as the frontend menu card payload."""
    cards = []
    for item in items:
        cards.append(
            {field: item.get(field, default) for field, default in MENU_CARD_FIELDS}
        )

    return {"type": "menu_cards", "items": cards}
