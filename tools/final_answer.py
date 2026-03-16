"""
final_answer Tool — 최종 응답 포맷팅.

Menu Agent: 검색 결과를 카드 JSON으로 포맷팅.
CS Agent: RAG 검색 결과 + 쿼리를 LLM에 넘겨 자연어 답변 생성.
"""

import json
from typing import List

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

load_dotenv()


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
        cards.append({
            "name":        item.get("name", ""),
            "category":    item.get("category", ""),
            "price":       item.get("price", 0),
            "description": item.get("description", ""),
            "allergy":     item.get("allergy", ""),
            "nutrition":   item.get("nutrition", ""),
            "options":     item.get("options", ""),
        })

    return json.dumps(
        {"type": "menu_cards", "items": cards},
        ensure_ascii=False,
    )


# ── CS Agent용 ───────────────────────────────────────────────────────────────

_cs_llm = None

def _get_cs_llm() -> ChatOpenAI:
    global _cs_llm
    if _cs_llm is None:
        _cs_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    return _cs_llm


@tool
def final_answer_cs(query: str, retrieved_docs: List[str]) -> str:
    """검색된 CS 사례를 바탕으로 고객 문의에 자연어 답변을 생성합니다.

    RAG 방식: retrieved_docs(검색 결과) + query(고객 문의) → LLM → 자연어 답변.

    Args:
        query: 고객의 원본 문의 내용.
        retrieved_docs: search_cs에서 반환된 관련 CS 사례 텍스트 리스트.

    Returns:
        자연어 답변 JSON 문자열. type="text"
    """
    context = "\n\n---\n\n".join(retrieved_docs)
    prompt = f"""당신은 BBQ 고객센터 상담사입니다.
아래 참고 자료를 바탕으로 고객 문의에 친절하고 명확하게 답변해 주세요.
참고 자료에 없는 내용은 임의로 만들지 마세요.

[참고 자료]
{context}

[고객 문의]
{query}

[답변]"""

    llm = _get_cs_llm()
    response = llm.invoke(prompt)
    answer = response.content.strip()

    return json.dumps(
        {"type": "text", "message": answer},
        ensure_ascii=False,
    )
