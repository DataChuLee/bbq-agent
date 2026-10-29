from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


PRICE_PATTERN = re.compile(r"(\d+)\s*만\s*원?|(\d{4,6})\s*원")
PRICE_ABOVE_TERMS = ("이상", "초과", "넘는", "비싼")

SPICINESS_RULES = [
    (("안매운", "덜매운", "안맵", "맵지않", "순한", "순함"), "순함"),
    (("매운", "매움", "맵고", "매워", "맵다", "맵게"), "매움"),
    (("보통",), "보통"),
]
TEXTURE_RULES = [
    (("바삭",), "바삭함"),
    (("부드러",), "부드러움"),
    (("쫄깃",), "쫄깃함"),
    (("촉촉",), "촉촉함"),
]
CATEGORY_RULES = [
    (("후라이드",), "후라이드"),
    (("구이",), "구이"),
    (("반반",), "반반"),
    (("시즈닝",), "시즈닝"),
    (("세트",), "세트메뉴"),
    (("1인분",), "1인분 메뉴"),
    (("신메뉴",), "신메뉴"),
]
PRODUCT_FAMILY_RULES = [
    (("버거",), "burger"),
    (("피자",), "pizza"),
    (("사이드", "감자튀김", "치즈볼", "콘립", "고추킹", "멘보샤"), "side"),
    (("음료", "콜라", "사이다", "스프라이트", "레몬보이"), "drink"),
    (("소스", "치킨무"), "sauce"),
    (("치킨", "닭", "윙", "봉", "순살", "반마리", "통다리"), "chicken"),
]
COOKING_METHOD_RULES = [
    (("구운", "구워", "그릴"), "grilled"),
    (("훈제",), "smoked"),
    (("튀긴", "튀겨"), "fried"),
    # "탕"은 맛탕까지 잡아서 쓰지 않는다.
    (("국물",), "soup"),
]
SAUCE_STYLE_RULES = [
    (("간장",), "soy_sauce"),
    (("스파이시소스", "매운소스", "매운양념"), "spicy_sauce"),
    (("양념",), "sauced"),
]
# "양념 말고 후라이드"처럼 빼달라는 대상은 조건으로 읽지 않도록 지운다.
EXCLUDED_TERM_PATTERN = re.compile(r"\S+\s*(말고|빼고|대신)")
# "매운 거 못 먹는"은 매운 단어가 있어도 순한 메뉴를 원하는 질의다.
SPICY_AVOID_TERMS = ("못먹", "싫어", "약해", "약한")
# 메뉴 데이터의 알레르기 표기에 쓰이는 재료명이다. "게"는 어미와 헷갈려 뺐다.
ALLERGEN_TERMS = (
    "우유", "땅콩", "대두", "밀", "새우", "돼지고기", "쇠고기", "닭고기",
    "토마토", "조개류", "오징어", "계란", "알류", "고등어", "아황산류",
)
ALLERGEN_PATTERN = re.compile(
    rf"({'|'.join(ALLERGEN_TERMS)})\s*(알레르기|알러지|안\s*들어간|없는|빼고|못\s*먹)"
)
RISKY_FILTER_KEYS = ("sauce_style", "product_family")
# 사용자가 명시적으로 요청한 조건이므로 {} 폴백 직전에 단독 필터로 한 번 더 시도한다.
NON_NEGOTIABLE_FILTER_KEYS = frozenset({"spiciness"})


def _match_rule(normalized: str, rules: list) -> str | None:
    for terms, value in rules:
        if any(term in normalized for term in terms):
            return value
    return None


def infer_sauce_style_filter(normalized: str) -> str | None:
    if "양념" in normalized and any(
        term in normalized for term in ("매운", "맵", "스파이시")
    ):
        return "spicy_sauce"
    return _match_rule(normalized, SAUCE_STYLE_RULES)


def extract_excluded_terms(query: str) -> list[str]:
    """빼달라고 한 재료나 메뉴 이름을 돌려준다. 메뉴명·설명·알레르기에 있으면 결과에서 뺀다."""
    terms = [m.group(1) for m in ALLERGEN_PATTERN.finditer(query)]
    terms += [m.group(0).split()[0].removesuffix(m.group(1)) for m in EXCLUDED_TERM_PATTERN.finditer(query)]
    if "계란" in terms:
        terms.append("알류")
    return [term for term in dict.fromkeys(terms) if term]


def extract_rule_based_filters(query: str) -> dict[str, Any]:
    query = EXCLUDED_TERM_PATTERN.sub("", query)
    normalized = query.replace(" ", "")
    filters: list[dict[str, Any]] = []

    match = PRICE_PATTERN.search(query)
    if match:
        price = int(match.group(1)) * 10000 if match.group(1) else int(match.group(2))
        op = "$gte" if any(term in query for term in PRICE_ABOVE_TERMS) else "$lte"
        filters.append({"price": {op: price}})

    if value := _match_rule(normalized, SPICINESS_RULES):
        if value == "매움" and any(term in normalized for term in SPICY_AVOID_TERMS):
            value = "순함"
        filters.append({"spiciness": {"$eq": value}})
    if value := _match_rule(normalized, TEXTURE_RULES):
        filters.append({"primary_texture": {"$eq": value}})
    if value := _match_rule(normalized, CATEGORY_RULES):
        filters.append({"category": {"$eq": value}})
    if value := _match_rule(normalized, PRODUCT_FAMILY_RULES):
        filters.append({"product_family": {"$eq": value}})
    if value := _match_rule(normalized, COOKING_METHOD_RULES):
        filters.append({"cooking_method": {"$eq": value}})
    if value := infer_sauce_style_filter(normalized):
        filters.append({"sauce_style": {"$eq": value}})

    if not filters:
        return {}
    return filters[0] if len(filters) == 1 else {"$and": filters}


def _filter_key(filter_part: dict[str, Any]) -> str | None:
    if len(filter_part) != 1:
        return None
    return next(iter(filter_part))


def _compact_filter(parts: list[dict[str, Any]]) -> dict[str, Any]:
    if not parts:
        return {}
    if len(parts) == 1:
        return deepcopy(parts[0])
    return {"$and": deepcopy(parts)}


def build_relaxed_filter_candidates(strict_filter: dict[str, Any]) -> list[dict[str, Any]]:
    if not strict_filter:
        return [{}]

    if "$and" not in strict_filter:
        return [deepcopy(strict_filter), {}]

    parts = list(strict_filter.get("$and") or [])
    candidates = [_compact_filter(parts)]
    current = parts

    for risky_key in RISKY_FILTER_KEYS:
        relaxed = [
            filter_part
            for filter_part in current
            if _filter_key(filter_part) != risky_key
        ]
        if relaxed != current:
            candidates.append(_compact_filter(relaxed))
            current = relaxed

    if candidates[-1] != {}:
        # spiciness 등 비협상 필터가 있으면 단독 필터를 {} 앞에 삽입한다.
        core = [fp for fp in parts if _filter_key(fp) in NON_NEGOTIABLE_FILTER_KEYS]
        if core:
            core_filter = _compact_filter(core)
            if core_filter != candidates[-1]:
                candidates.append(core_filter)
        candidates.append({})
    return candidates
