from __future__ import annotations

from typing import Literal


Intent = Literal["menu", "menu_followup", "cs", "unknown"]

ORDER_MARKERS = (
    "장바구니",
    "담아줘",
    "담아",
    "주문할게",
    "주문해줘",
    "이걸로주문",
    "이걸로할게",
    "결제하러",
)
FOLLOWUP_MARKERS = ("다른", "또", "더", "없어", "추가")

# 단순 "다른 거 없어?"가 아닌, 새로운 메뉴 조건을 명시한 팔로업을 구별하기 위한 키워드
_REFINE_KEYWORDS = frozenset((
    "바삭", "부드러", "쫄깃", "촉촉",          # 식감
    "안매운", "맵지않", "순한", "덜맵",          # 맵기
    "순살", "반마리",                            # 부위·사이즈
    "저렴", "싼", "얼마", "가격",               # 가격
    "사이드", "세트", "음료", "버거", "피자",   # 카테고리
    "알레르기",                                  # 알레르기
))
MENU_KEYWORDS = (
    "메뉴",
    "치킨",
    "추천",
    "가격",
    "얼마",
    "어떤",
    "있어",
    "사이드",
    "음료",
    "버거",
    "피자",
    "순살",
    "반마리",
    "바삭",
    "매운",
    "순한",
    "알레르기",
    "세트",
)
CS_KEYWORDS = (
    "배달",
    "배송",
    "환불",
    "환급",
    "클레임",
    "불만",
    "민원",
    "기프티콘",
    "오류",
    "에러",
    "이물질",
    "위생",
    "늦",
    "안와",
    "잘못",
    "불량",
    "항의",
    "컴플레인",
)


def _normalize(message: str) -> str:
    return message.replace(" ", "").lower()


def looks_like_order_request(message: str) -> bool:
    normalized = _normalize(message)
    return any(marker in normalized for marker in ORDER_MARKERS)


def has_new_menu_constraints(message: str) -> bool:
    """팔로업 메시지에 새로운 메뉴 조건(식감·맵기·가격 등)이 포함돼 있는지 확인한다."""
    normalized = _normalize(message)
    return any(kw in normalized for kw in _REFINE_KEYWORDS)


def looks_like_menu_followup(message: str, last_menu_query: object) -> bool:
    if not str(last_menu_query or "").strip():
        return False

    normalized = _normalize(message)
    return any(marker in normalized for marker in FOLLOWUP_MARKERS)


def heuristic_classify(
    message: str,
    *,
    last_menu_query: object = None,
) -> Intent | None:
    normalized = _normalize(message)
    if looks_like_order_request(message):
        return "menu"
    if looks_like_menu_followup(message, last_menu_query):
        return "menu_followup"

    cs_hits = sum(1 for keyword in CS_KEYWORDS if keyword in normalized)
    menu_hits = sum(1 for keyword in MENU_KEYWORDS if keyword in normalized)
    if cs_hits > menu_hits and cs_hits >= 2:
        return "cs"
    if menu_hits > cs_hits and menu_hits >= 2:
        return "menu"
    return None


def build_intent_prompt(message: str) -> str:
    return f"""Classify the user's message into exactly one intent.

- menu: BBQ menu recommendation, menu search, final menu selection, price/flavor/allergy/menu availability.
- cs: delivery delay, refund, complaint, gift certificate, existing order issue, customer service.
- unknown: anything else.

Answer with only one lowercase label: menu, cs, or unknown.

User message: {message}
Intent:"""
