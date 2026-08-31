import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain_core.messages import HumanMessage

from graph.intent import heuristic_classify


def test_heuristic_classify_routes_menu_without_llm() -> None:
    assert heuristic_classify("매운 치킨 메뉴 추천해줘") == "menu"


def test_heuristic_classify_routes_cs_without_llm() -> None:
    assert heuristic_classify("배달이 너무 늦어서 환불 받고 싶어요") == "cs"


def test_heuristic_classify_routes_menu_followup_when_previous_menu_query_exists() -> None:
    assert (
        heuristic_classify(
            "다른 건 없어?",
            last_menu_query="매운 치킨 추천해줘",
        )
        == "menu_followup"
    )


def test_heuristic_classify_defers_general_conversation_to_llm() -> None:
    assert heuristic_classify("오늘 기분이 좋아") is None


def test_intent_classifier_routes_general_conversation_to_unknown() -> None:
    from graph import graph as graph_module

    classifier = SimpleNamespace(
        ainvoke=AsyncMock(return_value=SimpleNamespace(content="unknown"))
    )
    state = {
        "messages": [HumanMessage(content="오늘 기분이 좋아")],
        "last_menu_query": None,
        "shown_menu_names": [],
        "menu_results": {},
        "cs_results": {},
        "selected_order": None,
    }

    with patch.object(graph_module, "_classifier_llm", classifier):
        result = asyncio.run(graph_module.intent_classifier_node(state))

    classifier.ainvoke.assert_awaited_once()
    assert result == {"intent": "unknown"}
