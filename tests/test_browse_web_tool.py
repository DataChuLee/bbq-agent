import unittest
from langchain_core.messages import HumanMessage


class BrowserGraphRoutingTests(unittest.TestCase):
    def test_web_intent_does_not_route_to_browser_agent(self) -> None:
        from graph.graph import route_intent

        self.assertEqual(route_intent({"intent": "web"}), "fallback")

    def test_order_intent_does_not_route_directly_to_order_browser_agent(self) -> None:
        from graph.graph import route_intent

        self.assertEqual(route_intent({"intent": "order"}), "fallback")

    def test_order_request_routes_to_order_browser_agent_after_menu_agent(self) -> None:
        from graph.graph import route_after_menu

        self.assertEqual(
            route_after_menu(
                {
                    "intent": "menu",
                    "messages": [
                        HumanMessage(
                            content="황금올리브 치킨에 콜라 옵션으로 장바구니에 담아줘"
                        )
                    ],
                }
            ),
            "order_browser_agent",
        )

    def test_selected_order_routes_to_order_browser_agent_after_menu_agent(self) -> None:
        from graph.graph import route_after_menu

        self.assertEqual(
            route_after_menu(
                {
                    "intent": "menu",
                    "messages": [HumanMessage(content="이 메뉴로 진행할게")],
                    "selected_order": {
                        "menu_name": "황금올리브치킨",
                        "options": ["콜라 1.25L"],
                        "order_type": "delivery",
                    },
                }
            ),
            "order_browser_agent",
        )

    def test_non_order_menu_request_ends_after_menu_agent(self) -> None:
        from graph.graph import route_after_menu

        self.assertEqual(
            route_after_menu(
                {"intent": "menu", "messages": [HumanMessage(content="매운 치킨 추천해줘")]}
            ),
            "end",
        )

    def test_order_agent_tools_include_prepare_bbq_order(self) -> None:
        from graph.graph import _order_tools

        self.assertIn("prepare_bbq_order", [tool.name for tool in _order_tools])

    def test_cs_agent_tools_do_not_include_browser_use(self) -> None:
        from graph.graph import _cs_tools

        self.assertNotIn("prepare_bbq_order", [tool.name for tool in _cs_tools])


if __name__ == "__main__":
    unittest.main()
