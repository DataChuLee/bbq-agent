import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import HumanMessage


class DummyClassifier:
    def __init__(self) -> None:
        self.ainvoke = AsyncMock()


class MenuFollowupIntentTests(unittest.IsolatedAsyncioTestCase):
    async def test_followup_request_uses_menu_followup_intent_without_llm(self) -> None:
        from graph import graph as graph_module

        state = {
            "messages": [HumanMessage(content="다른 건 없어?")],
            "last_menu_query": "매운 치킨 추천해줘",
            "shown_menu_names": ["뿜치킹"],
            "menu_results": {},
            "cs_results": {},
            "selected_order": None,
        }

        dummy_classifier = DummyClassifier()
        with patch.object(graph_module, "_classifier_llm", dummy_classifier):
            result = await graph_module.intent_classifier_node(state)

        dummy_classifier.ainvoke.assert_not_called()
        self.assertEqual(result["intent"], "menu_followup")

    async def test_order_request_takes_priority_over_followup_intent(self) -> None:
        from graph import graph as graph_module

        state = {
            "messages": [HumanMessage(content="다른 건 말고 이걸로 주문 준비해줘")],
            "last_menu_query": "매운 치킨 추천해줘",
            "shown_menu_names": ["뿜치킹"],
            "menu_results": {},
            "cs_results": {},
            "selected_order": None,
        }

        dummy_classifier = DummyClassifier()
        with patch.object(graph_module, "_classifier_llm", dummy_classifier):
            result = await graph_module.intent_classifier_node(state)

        dummy_classifier.ainvoke.assert_not_called()
        self.assertEqual(result["intent"], "menu")


class MenuFollowupNodeTests(unittest.IsolatedAsyncioTestCase):
    async def test_followup_node_excludes_already_shown_items_and_returns_cards(self) -> None:
        from graph import graph as graph_module

        search_results = [
            {"name": "뿜치킹", "category": "신메뉴", "price": 24000},
            {"name": "스모크치킨", "category": "구이", "price": 22000},
            {"name": "황금올리브치킨™핫크리스피", "category": "후라이드", "price": 24000},
            {"name": "자메이카 통다리구이", "category": "구이", "price": 21500},
        ]
        state = {
            "messages": [HumanMessage(content="다른 건 없어?")],
            "last_menu_query": "매운 치킨 추천해줘",
            "shown_menu_names": ["뿜치킹"],
            "menu_results": {"매운 치킨 추천해줘": [search_results[0]]},
            "cs_results": {},
            "selected_order": None,
        }

        with patch.object(
            graph_module,
            "search_menu_results",
            return_value=search_results,
        ) as mock_search:
            result = await graph_module.menu_followup_node(state)

        mock_search.assert_called_once()
        self.assertEqual(result["response"]["type"], "menu_cards")
        self.assertEqual(
            [item["name"] for item in result["response"]["items"]],
            ["스모크치킨", "황금올리브치킨™핫크리스피", "자메이카 통다리구이"],
        )
        self.assertEqual(
            result["shown_menu_names"],
            ["뿜치킹", "스모크치킨", "황금올리브치킨™핫크리스피", "자메이카 통다리구이"],
        )

    async def test_followup_node_returns_text_when_no_new_items_exist(self) -> None:
        from graph import graph as graph_module

        state = {
            "messages": [HumanMessage(content="다른 건 없어?")],
            "last_menu_query": "매운 치킨 추천해줘",
            "shown_menu_names": ["뿜치킹"],
            "menu_results": {},
            "cs_results": {},
            "selected_order": None,
        }

        with patch.object(
            graph_module,
            "search_menu_results",
            return_value=[{"name": "뿜치킹", "category": "신메뉴", "price": 24000}],
        ):
            result = await graph_module.menu_followup_node(state)

        self.assertEqual(result["response"]["type"], "text")
        self.assertIn("다른 메뉴", result["response"]["message"])
        self.assertEqual(result["shown_menu_names"], ["뿜치킹"])

    async def test_followup_with_new_constraints_searches_current_message(self) -> None:
        from graph import graph as graph_module

        current_message = "그럼 안 매운 다른 메뉴 추천해줘"
        selected_order = {
            "menu_name": "뿜치킹",
            "options": [],
            "order_type": "delivery",
        }
        state = {
            "messages": [HumanMessage(content=current_message)],
            "last_menu_query": "매운 치킨 추천해줘",
            "shown_menu_names": ["뿜치킹"],
            "menu_results": {},
            "cs_results": {},
            "selected_order": selected_order,
        }
        search_results = [
            {"name": "황금올리브치킨™", "category": "후라이드", "price": 23000}
        ]

        with patch.object(
            graph_module,
            "search_menu_results",
            return_value=search_results,
        ) as mock_search:
            result = await graph_module.menu_followup_node(state)

        mock_search.assert_called_once_with(
            current_message,
            state,
            k=graph_module.FOLLOWUP_TOP_K,
            use_cache=False,
        )
        self.assertEqual(result["last_menu_query"], current_message)
        self.assertEqual(result["response"]["type"], "menu_cards")
        self.assertNotIn("selected_order", result)
        self.assertEqual(state["selected_order"], selected_order)


if __name__ == "__main__":
    unittest.main()
