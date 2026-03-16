"""
BBQ Agent LangGraph StateGraph.

흐름:
  START → intent_classifier
        → (menu)    menu_agent_node (create_react_agent wrapper) → END
        → (cs)      cs_agent_node   (create_react_agent wrapper) → END
        → (unknown) fallback                                      → END
"""

import json
from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent

from graph.state import AgentState
from tools.ask_clarification import ask_clarification
from tools.final_answer import final_answer_cs, final_answer_menu
from tools.search_cs import search_cs
from tools.search_menu import search_menu

load_dotenv()

# ── 시스템 프롬프트 ──────────────────────────────────────────────────────────

MENU_SYSTEM_PROMPT = """당신은 BBQ 치킨 메뉴 추천 전문 AI입니다.
사용자가 원하는 메뉴를 찾을 수 있도록 도와주세요.

사용 가능한 도구:
- search_menu: 자연어로 메뉴를 검색합니다. 가격, 카테고리, 알레르기 조건 포함 가능.
- ask_clarification: 쿼리가 모호할 때 사용자에게 추가 정보를 요청합니다.
- final_answer_menu: 검색 결과를 카드 형태로 최종 응답합니다.

반드시 final_answer_menu 또는 ask_clarification으로 응답을 마무리하세요."""

CS_SYSTEM_PROMPT = """당신은 BBQ 고객센터 AI 상담사입니다.
고객의 문의에 친절하고 정확하게 답변해 주세요.

사용 가능한 도구:
- search_cs: 유사한 CS 사례를 검색합니다.
- final_answer_cs: 검색 결과를 바탕으로 최종 답변을 생성합니다.

반드시 final_answer_cs로 응답을 마무리하세요."""

# ── create_react_agent 인스턴스 (모듈 로드 시 1회 생성) ─────────────────────

_menu_tools = [search_menu, ask_clarification, final_answer_menu]
_cs_tools   = [search_cs, final_answer_cs]

_menu_agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o-mini", temperature=0),
    tools=_menu_tools,
    prompt=MENU_SYSTEM_PROMPT,
)

_cs_agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o-mini", temperature=0),
    tools=_cs_tools,
    prompt=CS_SYSTEM_PROMPT,
)

# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _extract_response(messages: list) -> dict:
    """messages를 역순 탐색해 final_answer / ask_clarification Tool 결과를 반환."""
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            try:
                data = json.loads(msg.content)
                if "type" in data:  # menu_cards / text / clarification
                    return data
            except Exception:
                continue
    return {"type": "text", "message": "응답을 생성하지 못했습니다."}


# ── Node 함수 ────────────────────────────────────────────────────────────────

def intent_classifier_node(state: AgentState) -> dict:
    """사용자 입력의 의도를 분류 → menu / cs / unknown"""
    last_message = state["messages"][-1].content
    prompt = f"""사용자 메시지를 보고 의도를 분류하세요.

- menu: BBQ 메뉴 추천, 메뉴 검색, 어떤 메뉴가 있는지 등
- cs: 배달 지연, 환불, 불만, 기프티콘, 주문 문의 등 고객 서비스 관련
- unknown: 위 두 가지에 해당하지 않는 경우

반드시 menu, cs, unknown 중 하나만 소문자로 답하세요.

사용자 메시지: {last_message}
의도:"""

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    response = llm.invoke(prompt)
    intent = response.content.strip().lower()
    if intent not in ("menu", "cs"):
        intent = "unknown"

    return {"intent": intent}


def menu_agent_node(state: AgentState) -> dict:
    """Menu Agent — create_react_agent 기반 ReAct 루프"""
    result = _menu_agent.invoke({"messages": state["messages"]})
    return {
        "messages": result["messages"],
        "response": _extract_response(result["messages"]),
    }


def cs_agent_node(state: AgentState) -> dict:
    """CS Agent — create_react_agent 기반 ReAct 루프"""
    result = _cs_agent.invoke({"messages": state["messages"]})
    return {
        "messages": result["messages"],
        "response": _extract_response(result["messages"]),
    }


def fallback_node(state: AgentState) -> dict:
    """unknown 의도 — 안내 메시지 반환"""
    return {
        "response": {
            "type": "text",
            "message": "안녕하세요! BBQ AI입니다.\n메뉴 추천이나 주문 관련 문의를 도와드릴 수 있습니다.\n예: '매운 치킨 추천해줘', '환불하고 싶어요'",
        }
    }


# ── 라우팅 함수 ──────────────────────────────────────────────────────────────

def route_intent(state: AgentState) -> Literal["menu_agent", "cs_agent", "fallback"]:
    intent = state.get("intent", "unknown")
    if intent == "menu":
        return "menu_agent"
    elif intent == "cs":
        return "cs_agent"
    return "fallback"


# ── Graph 조립 ────────────────────────────────────────────────────────────────

def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("intent_classifier", intent_classifier_node)
    builder.add_node("menu_agent", menu_agent_node)
    builder.add_node("cs_agent", cs_agent_node)
    builder.add_node("fallback", fallback_node)

    builder.add_edge(START, "intent_classifier")
    builder.add_conditional_edges(
        "intent_classifier",
        route_intent,
        {
            "menu_agent": "menu_agent",
            "cs_agent":   "cs_agent",
            "fallback":   "fallback",
        },
    )
    builder.add_edge("menu_agent", END)
    builder.add_edge("cs_agent",   END)
    builder.add_edge("fallback",   END)

    return builder.compile()


# 싱글턴 그래프 인스턴스
graph = build_graph()
