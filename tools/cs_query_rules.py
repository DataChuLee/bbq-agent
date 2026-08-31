from __future__ import annotations


SPELL_DICT: dict[str, str] = {
    "환뷸": "환불",
    "배딜": "배달",
    "주뭉": "주문",
    "기프티곤": "기프티콘",
    "이물직": "이물질",
    "뷸량": "불량",
    "위상": "위생",
    "클레입": "클레임",
}


def keep_cs_query(query: str) -> str:
    """원문 표현을 보존해 벡터와 키워드 검색 모두에 전달한다."""
    return query

CS_SYNONYMS: dict[str, list[str]] = {
    "환불": ["환급", "반환", "결제취소"],
    "배달": ["배송", "딜리버리", "배달부"],
    "불량": ["결함", "하자", "불만족"],
    "오류": ["에러", "오작동", "작동불가"],
    "기프티콘": ["기프트콘", "모바일쿠폰"],
}


def correct_cs_spelling(query: str) -> str:
    """검색 의도를 바꾸지 않는 명백한 오타만 교정한다."""
    normalized = query
    for wrong, right in SPELL_DICT.items():
        normalized = normalized.replace(wrong, right)
    return normalized


def normalize_cs_synonyms(query: str) -> str:
    """동일 의미로 판단한 표현을 대표 키워드로 치환한다."""
    normalized = query
    for canonical, synonyms in CS_SYNONYMS.items():
        for synonym in synonyms:
            normalized = normalized.replace(synonym, canonical)
    return normalized


def preprocess_cs_query(query: str) -> str:
    """기존 평가 호환성을 위해 오타 교정과 유의어 정규화를 함께 적용한다."""
    return normalize_cs_synonyms(correct_cs_spelling(query))
