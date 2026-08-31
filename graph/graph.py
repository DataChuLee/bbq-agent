"""
BBQ Agent LangGraph StateGraph.

Flow:
    START -> intent_classifier
          -> menu_agent -> (order_browser_agent | END)
          -> cs_agent   -> END
          -> fallback   -> END
"""

from __future__ import annotations

import json
import re
import asyncio
from typing import Annotated, List, Literal, Optional, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.managed import RemainingSteps
from langgraph.prebuilt import create_react_agent

from graph.intent import (
    build_intent_prompt,
    has_new_menu_constraints,
    heuristic_classify,
    looks_like_menu_followup,
    looks_like_order_request,
)
from graph.state import AgentState
from tools.final_answer import format_menu_cards
from tools.prepare_bbq_order import prepare_bbq_order
from tools.search_cs import search_cs
from tools.search_menu import FOLLOWUP_TOP_K, NO_MATCH_MESSAGE, search_menu_results


load_dotenv()


class _ReActState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    remaining_steps: Annotated[int, RemainingSteps()]
    menu_results: Optional[dict]
    cs_results: Optional[dict]
    selected_order: Optional[dict]
    last_menu_query: Optional[str]
    shown_menu_names: list[str]


FOLLOWUP_DISPLAY_LIMIT = 3


CS_SYSTEM_PROMPT = """You are a BBQ customer service assistant.

Always follow this order:
1. Use search_cs(query) to search relevant customer-service cases.
2. Answer the customer's question clearly and politely based on the retrieved cases.
   - Do not invent information that was not found.
   - Do not use browser automation or order placement tools."""

ORDER_SYSTEM_PROMPT = """You are the BBQ order preparation assistant.

You run only after the user has chosen a final chicken/menu item and options through
the menu flow. Use prepare_bbq_order(menu_name, options, order_type) to open the BBQ
website in a visible browser and prepare the chosen item/options in the cart.

Rules:
- Never ask for or handle the user's BBQ credentials.
- Login, address selection, and payment must be done by the user directly in the browser.
- If menu_name, options, or order_type is unclear, ask a short clarification question.
- Do not use this tool for customer-service questions or general web browsing."""


_cs_tools = [search_cs]
_order_tools = [prepare_bbq_order]

_classifier_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
_fallback_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, streaming=True)

_cs_agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o-mini", temperature=0, streaming=True),
    tools=_cs_tools,
    prompt=CS_SYSTEM_PROMPT,
    state_schema=_ReActState,
)

_order_agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o-mini", temperature=0, streaming=True),
    tools=_order_tools,
    prompt=ORDER_SYSTEM_PROMPT,
    state_schema=_ReActState,
)


def _extract_response(messages: list) -> dict:
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            try:
                data = json.loads(msg.content)
                if "type" in data:
                    return data
            except Exception:
                continue
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
            return {"type": "text", "message": msg.content}
    return {"type": "text", "message": "\uc751\ub2f5\uc744 \uc0dd\uc131\ud558\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4."}


def _latest_user_message(state: dict) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""


def _normalize_menu_text(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", value.replace("™", "")).lower()


def _looks_like_order_request(message: str) -> bool:
    return looks_like_order_request(message)


def _looks_like_menu_followup(message: str, state: dict) -> bool:
    return looks_like_menu_followup(message, state.get("last_menu_query"))


def _append_shown_menu_names(
    shown_menu_names: object,
    items: list[dict],
) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    if isinstance(shown_menu_names, list):
        for value in shown_menu_names:
            name = str(value or "").strip()
            if not name or name in seen:
                continue
            names.append(name)
            seen.add(name)

    for item in items:
        name = str(item.get("name") or "").strip()
        if not name or name in seen:
            continue
        names.append(name)
        seen.add(name)

    return names


def _unseen_menu_items(items: list[dict], shown_menu_names: object) -> list[dict]:
    shown = {
        str(name).strip()
        for name in (shown_menu_names if isinstance(shown_menu_names, list) else [])
        if str(name or "").strip()
    }
    unseen: list[dict] = []
    seen = set(shown)

    for item in items:
        name = str(item.get("name") or "").strip()
        if not name or name in seen:
            continue
        unseen.append(item)
        seen.add(name)

    return unseen


def _menu_candidates_from_results(menu_results: dict | None) -> list[dict]:
    if not isinstance(menu_results, dict):
        return []

    candidates: list[dict] = []
    seen_names: set[str] = set()
    for results in menu_results.values():
        if not isinstance(results, list):
            continue
        for item in results:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name or name in seen_names:
                continue
            candidates.append(item)
            seen_names.add(name)
    return candidates


def _collect_option_names(value: object) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            return _collect_option_names(json.loads(text))
        except json.JSONDecodeError:
            return []

    if isinstance(value, list):
        names: list[str] = []
        for item in value:
            names.extend(_collect_option_names(item))
        return names

    if isinstance(value, dict):
        names = []
        name = str(value.get("name") or "").strip()
        if name:
            names.append(name)
        for key in ("items", "required_select", "optional_select"):
            names.extend(_collect_option_names(value.get(key)))
        return names

    return []


def _extract_options_for_direct_order(message: str, menu_item: dict) -> list[str]:
    normalized_message = _normalize_menu_text(message)
    option_names = _collect_option_names(menu_item.get("options", ""))
    if not option_names:
        option_names = [
            "한마리",
            "반마리",
            "순살 변경",
            "닭다리 변경",
            "윙&봉 변경",
            "콤보 변경",
            "콜라 1.25L",
            "콜라1.25L",
            "제로콜라1.25L",
        ]

    selected: list[str] = []
    seen_normalized: set[str] = set()
    for option_name in option_names:
        normalized_option = _normalize_menu_text(option_name)
        if not normalized_option or normalized_option not in normalized_message:
            continue
        if normalized_option in seen_normalized:
            continue
        selected.append(option_name)
        seen_normalized.add(normalized_option)
    return selected


def _extract_order_type(message: str) -> Literal["delivery", "pickup"]:
    normalized = message.replace(" ", "")
    if "포장" in normalized or "픽업" in normalized:
        return "pickup"
    return "delivery"


def _clarification_for_menu_candidates(candidates: list[dict]) -> dict:
    names = [str(item.get("name")) for item in candidates[:3] if item.get("name")]
    suffix = f" 후보: {', '.join(names)}" if names else ""
    return {
        "type": "clarification",
        "message": f"어떤 메뉴로 주문 준비할까요? 정확한 메뉴명을 선택해 주세요.{suffix}",
    }


def _resolve_direct_order_from_menu_results(state: AgentState) -> dict | None:
    message = _latest_user_message(state)
    candidates = _menu_candidates_from_results(state.get("menu_results"))
    if not candidates:
        return {"clarification": _clarification_for_menu_candidates(candidates)}

    normalized_message = _normalize_menu_text(message)
    matches = [
        item
        for item in candidates
        if _normalize_menu_text(str(item.get("name") or "")) in normalized_message
    ]
    if not matches:
        return {"clarification": _clarification_for_menu_candidates(candidates)}

    matches.sort(
        key=lambda item: len(_normalize_menu_text(str(item.get("name") or ""))),
        reverse=True,
    )
    top_length = len(_normalize_menu_text(str(matches[0].get("name") or "")))
    same_length_matches = [
        item
        for item in matches
        if len(_normalize_menu_text(str(item.get("name") or ""))) == top_length
    ]
    if len(same_length_matches) > 1:
        return {"clarification": _clarification_for_menu_candidates(same_length_matches)}

    menu_item = matches[0]
    return {
        "order": {
            "menu_name": str(menu_item["name"]),
            "menu_category": str(menu_item.get("category") or ""),
            "options": _extract_options_for_direct_order(message, menu_item),
            "order_type": _extract_order_type(message),
        }
    }


def _extract_order_tool_response(content: str) -> dict:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return {"type": "text", "message": content}

    if payload.get("type") == "order_status":
        status = str(payload.get("status") or "cart_ready")
        menu_name = str(payload.get("menu_name") or "").strip() or "선택한 메뉴"
        return {
            "type": "order_status",
            "status": status,
            "message": str(
                payload.get("message")
                or (
                    f"{menu_name}의 옵션 확인이 필요해요."
                    if status == "option_review"
                    else f"{menu_name}이 장바구니에 담겼어요."
                )
            ),
            "menu_name": menu_name,
            "expected_options": payload.get("expected_options") or [],
            "selected_options": payload.get("selected_options") or [],
            "missing_options": payload.get("missing_options") or [],
            "order_type": str(payload.get("order_type") or ""),
            "current_url": str(payload.get("current_url") or ""),
            "next_action": str(
                payload.get("next_action")
                or "BBQ 공식 사이트에서 장바구니와 결제를 확인해 주세요."
            ),
        }

    if payload.get("ok"):
        return {
            "type": "text",
            "message": str(payload.get("result") or "주문 준비를 시작했습니다."),
        }

    return {
        "type": "text",
        "message": str(payload.get("error") or "주문 준비 중 오류가 발생했습니다."),
    }


async def intent_classifier_node(state: AgentState) -> dict:
    """Classify initial request only as menu, cs, or unknown."""
    last_message = str(state["messages"][-1].content)
    heuristic_intent = heuristic_classify(
        last_message,
        last_menu_query=state.get("last_menu_query"),
    )
    if heuristic_intent:
        return {"intent": heuristic_intent}

    response = await _classifier_llm.ainvoke(build_intent_prompt(last_message))
    intent = response.content.strip().lower()
    if intent not in ("menu", "cs"):
        intent = "unknown"
    return {"intent": intent}


def _extract_new_search_entry(messages: list, tool_name: str) -> tuple[str, list] | None:
    query = None
    for msg in messages:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            for tool_call in msg.tool_calls:
                if tool_call.get("name") == tool_name:
                    query = tool_call.get("args", {}).get("query")
                    break
        if query:
            break

    if not query:
        return None

    for msg in messages:
        if isinstance(msg, ToolMessage) and getattr(msg, "name", "") == tool_name:
            try:
                data = json.loads(msg.content)
                results = data.get("results")
                if results:
                    return query, results
            except Exception:
                continue
    return None


async def menu_agent_node(state: AgentState) -> dict:
    query = _latest_user_message(state).strip()
    if _looks_like_order_request(query):
        return {"messages": []}

    results = await asyncio.to_thread(search_menu_results, query, dict(state))
    if not results:
        return {
            "messages": [AIMessage(content=NO_MATCH_MESSAGE)],
            "response": {"type": "text", "message": NO_MATCH_MESSAGE},
        }

    cache = dict(state.get("menu_results") or {})
    cache[query] = results

    return {
        "messages": [AIMessage(content="메뉴 검색 결과를 카드로 준비했습니다.")],
        "response": format_menu_cards(results),
        "menu_results": cache,
        "last_menu_query": query,
        "shown_menu_names": _append_shown_menu_names(
            state.get("shown_menu_names") or [],
            results,
        ),
    }


async def menu_followup_node(state: AgentState) -> dict:
    last_query = str(state.get("last_menu_query") or "").strip()
    shown_menu_names = state.get("shown_menu_names") or []

    # 새로운 조건(식감·맵기·카테고리 등)이 있으면 현재 메시지로 검색한다
    current_message = _latest_user_message(state)
    query = current_message if has_new_menu_constraints(current_message) else last_query

    if not query:
        message = "이전 추천 조건을 찾지 못했습니다. 원하는 메뉴 조건을 다시 알려주세요."
        return {
            "messages": [AIMessage(content=message)],
            "response": {"type": "text", "message": message},
            "shown_menu_names": shown_menu_names,
        }

    results = await asyncio.to_thread(
        search_menu_results,
        query,
        dict(state),
        k=FOLLOWUP_TOP_K,
        use_cache=False,
    )
    items = _unseen_menu_items(results, shown_menu_names)[:FOLLOWUP_DISPLAY_LIMIT]
    if not items:
        message = "조건에 맞는 다른 메뉴를 더 찾지 못했습니다. 조건을 바꿔서 다시 말씀해주세요."
        return {
            "messages": [AIMessage(content=message)],
            "response": {"type": "text", "message": message},
            "last_menu_query": query,
            "shown_menu_names": shown_menu_names,
        }

    return {
        "messages": [
            AIMessage(content=f"다른 추천 메뉴 {len(items)}가지를 골라봤어요.")
        ],
        "response": format_menu_cards(items),
        "last_menu_query": query,
        "shown_menu_names": _append_shown_menu_names(shown_menu_names, items),
    }


async def cs_agent_node(state: AgentState) -> dict:
    original_count = len(state["messages"])
    result = await _cs_agent.ainvoke(
        {
            "messages": state["messages"],
            "menu_results": state.get("menu_results"),
            "cs_results": state.get("cs_results"),
            "selected_order": state.get("selected_order"),
        }
    )
    new_messages = result["messages"][original_count:]

    return_dict: dict = {
        "messages": new_messages,
        "response": _extract_response(result["messages"]),
    }
    entry = _extract_new_search_entry(new_messages, "search_cs")
    if entry:
        query, results = entry
        cache = dict(state.get("cs_results") or {})
        cache[query] = results
        return_dict["cs_results"] = cache
        return_dict["last_cs_query"] = query
    return return_dict


async def order_browser_agent_node(state: AgentState) -> dict:
    selected_order = state.get("selected_order")
    if selected_order:
        tool_kwargs = {"menu_category": selected_order.get("menu_category", "")}
        if selected_order.get("option_details"):
            tool_kwargs["option_details"] = selected_order.get("option_details")
        content = await asyncio.to_thread(
            prepare_bbq_order.func,
            selected_order["menu_name"],
            selected_order.get("options", []),
            selected_order["order_type"],
            dict(state),
            **tool_kwargs,
        )
        response = _extract_order_tool_response(content)
        message = AIMessage(content=response["message"])
        return {
            "messages": [message],
            "response": response,
            "selected_order": None,
        }

    direct_resolution = _resolve_direct_order_from_menu_results(state)
    if direct_resolution:
        direct_order = direct_resolution.get("order")
        if direct_order:
            content = await asyncio.to_thread(
                prepare_bbq_order.func,
                direct_order["menu_name"],
                direct_order.get("options", []),
                direct_order["order_type"],
                dict(state),
                menu_category=direct_order.get("menu_category", ""),
            )
            response = _extract_order_tool_response(content)
            message = AIMessage(content=response["message"])
            return {
                "messages": [message],
                "response": response,
                "selected_order": None,
            }

        clarification = direct_resolution["clarification"]
        message = AIMessage(content=clarification["message"])
        return {
            "messages": [message],
            "response": clarification,
            "selected_order": None,
        }

    original_count = len(state["messages"])
    result = await _order_agent.ainvoke(
        {
            "messages": state["messages"],
            "menu_results": state.get("menu_results"),
            "cs_results": state.get("cs_results"),
            "selected_order": state.get("selected_order"),
        }
    )
    new_messages = result["messages"][original_count:]

    return {
        "messages": new_messages,
        "response": _extract_response(result["messages"]),
    }


async def fallback_node(state: AgentState) -> dict:
    system = SystemMessage(
        content=(
            "\ub2f9\uc2e0\uc740 BBQ AI \uc5b4\uc2dc\uc2a4\ud134\ud2b8\uc785\ub2c8\ub2e4. "
            "\uba54\ub274 \ucd94\ucc9c, \uace0\uac1d \uc11c\ube44\uc2a4 \ubb38\uc758, "
            "\ub610\ub294 \ucd5c\uc885 \uc120\ud0dd \ud6c4 \uc8fc\ubb38 \uc900\ube44 \uc694\uccad\uc744 \ub3c4\uc640\ub4dc\ub9bd\ub2c8\ub2e4."
        )
    )
    ai_response = await _fallback_llm.ainvoke([system] + list(state["messages"]))
    ai_message = AIMessage(content=ai_response.content)
    return {
        "messages": [ai_message],
        "response": {"type": "text", "message": ai_response.content},
    }


def route_intent(
    state: AgentState,
) -> Literal["menu_agent", "menu_followup", "cs_agent", "fallback"]:
    intent = state.get("intent", "unknown")
    if intent == "menu":
        return "menu_agent"
    if intent == "menu_followup":
        return "menu_followup"
    if intent == "cs":
        return "cs_agent"
    return "fallback"


def route_after_menu(state: AgentState) -> Literal["order_browser_agent", "end"]:
    if state.get("selected_order"):
        return "order_browser_agent"
    if _looks_like_order_request(_latest_user_message(state)):
        return "order_browser_agent"
    return "end"


def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("intent_classifier", intent_classifier_node)
    builder.add_node("menu_agent", menu_agent_node)
    builder.add_node("menu_followup", menu_followup_node)
    builder.add_node("cs_agent", cs_agent_node)
    builder.add_node("order_browser_agent", order_browser_agent_node)
    builder.add_node("fallback", fallback_node)

    builder.add_edge(START, "intent_classifier")
    builder.add_conditional_edges(
        "intent_classifier",
        route_intent,
        {
            "menu_agent": "menu_agent",
            "menu_followup": "menu_followup",
            "cs_agent": "cs_agent",
            "fallback": "fallback",
        },
    )
    builder.add_conditional_edges(
        "menu_agent",
        route_after_menu,
        {
            "order_browser_agent": "order_browser_agent",
            "end": END,
        },
    )
    builder.add_edge("menu_followup", END)
    builder.add_edge("cs_agent", END)
    builder.add_edge("order_browser_agent", END)
    builder.add_edge("fallback", END)

    return builder.compile()


graph = build_graph()
