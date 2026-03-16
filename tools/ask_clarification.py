"""
ask_clarification Tool — 모호한 쿼리일 때 사용자에게 재질문.

LLM이 자율 판단으로 호출. 재질문 메시지를 반환하면
graph 레벨에서 사용자 답변을 기다린 후 루프를 재개.
"""

import json

from langchain_core.tools import tool


@tool
def ask_clarification(question: str) -> str:
    """메뉴 추천을 위해 사용자에게 추가 정보를 요청합니다.

    쿼리가 모호하거나 조건이 불충분할 때 호출합니다.
    예: 인원수, 매운 정도, 가격대, 선호 스타일 등.

    Args:
        question: 사용자에게 물어볼 구체적인 질문.
                  예: "몇 명이서 드실 건가요?", "얼마 정도 생각하고 계세요?"

    Returns:
        재질문 JSON 문자열 (graph에서 사용자 응답 대기 신호로 사용)
    """
    return json.dumps(
        {"type": "clarification", "question": question},
        ensure_ascii=False,
    )
