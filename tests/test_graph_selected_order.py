import json
import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import HumanMessage


class SelectedOrderGraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_order_browser_node_returns_order_status_payload(self) -> None:
        from graph.graph import order_browser_agent_node

        selected_order = {
            "menu_name": "Golden Olive",
            "menu_category": "Fried",
            "options": ["Coke 1.25L"],
            "order_type": "pickup",
        }

        with patch("graph.graph.prepare_bbq_order.func") as mock_prepare:
            mock_prepare.return_value = json.dumps(
                {
                    "ok": True,
                    "type": "order_status",
                    "status": "cart_ready",
                    "result": "Cart is ready.",
                    "menu_name": "Golden Olive",
                    "expected_options": ["Coke 1.25L"],
                    "order_type": "pickup",
                    "current_url": "https://www.bbq.co.kr/order/cart",
                    "next_action": "Review the cart in the open BBQ browser.",
                },
                ensure_ascii=False,
            )

            result = await order_browser_agent_node(
                {
                    "messages": [HumanMessage(content="prepare this order")],
                    "selected_order": selected_order,
                    "menu_results": {},
                    "cs_results": {},
                }
            )

        self.assertEqual(result["response"]["type"], "order_status")
        self.assertEqual(result["response"]["status"], "cart_ready")
        self.assertEqual(
            result["response"]["message"], "Golden Olive이 장바구니에 담겼어요."
        )
        self.assertEqual(result["response"]["menu_name"], "Golden Olive")
        self.assertEqual(result["response"]["expected_options"], ["Coke 1.25L"])
        self.assertEqual(
            result["response"]["current_url"], "https://www.bbq.co.kr/order/cart"
        )

    async def test_order_browser_node_passes_option_details_when_present(self) -> None:
        from graph.graph import order_browser_agent_node

        selected_order = {
            "menu_name": "Golden Olive",
            "menu_category": "Fried",
            "options": ["Coke 1.25L"],
            "option_details": [
                {
                    "group_name": "Drink selection",
                    "option_name": "Coke 1.25L",
                    "add_price": 1500,
                    "required": True,
                }
            ],
            "order_type": "delivery",
        }

        with patch("graph.graph.prepare_bbq_order.func") as mock_prepare:
            mock_prepare.return_value = json.dumps(
                {"ok": True, "type": "order_status", "message": "Cart is ready"},
                ensure_ascii=False,
            )

            await order_browser_agent_node(
                {
                    "messages": [HumanMessage(content="prepare this order")],
                    "selected_order": selected_order,
                    "menu_results": {},
                    "cs_results": {},
                }
            )

        mock_prepare.assert_called_once_with(
            "Golden Olive",
            ["Coke 1.25L"],
            "delivery",
            {
                "messages": [HumanMessage(content="prepare this order")],
                "selected_order": selected_order,
                "menu_results": {},
                "cs_results": {},
            },
            menu_category="Fried",
            option_details=selected_order["option_details"],
        )

    async def test_order_browser_node_uses_structured_selected_order(self) -> None:
        from graph.graph import order_browser_agent_node

        selected_order = {
            "menu_name": "황금올리브치킨",
            "menu_category": "후라이드",
            "options": ["콜라 1.25L", "치즈볼"],
            "order_type": "delivery",
        }

        with patch("graph.graph.prepare_bbq_order.func") as mock_prepare:
            mock_prepare.return_value = json.dumps(
                {"ok": True, "result": "장바구니 준비가 완료되었습니다."},
                ensure_ascii=False,
            )

            result = await order_browser_agent_node(
                {
                    "messages": [HumanMessage(content="이걸로 주문 준비해줘")],
                    "selected_order": selected_order,
                    "menu_results": {},
                    "cs_results": {},
                }
            )

        mock_prepare.assert_called_once_with(
            "황금올리브치킨",
            ["콜라 1.25L", "치즈볼"],
            "delivery",
            {
                "messages": [HumanMessage(content="이걸로 주문 준비해줘")],
                "selected_order": selected_order,
                "menu_results": {},
                "cs_results": {},
            },
            menu_category="후라이드",
        )
        self.assertEqual(
            result["response"],
            {"type": "text", "message": "장바구니 준비가 완료되었습니다."},
        )
        self.assertIsNone(result["selected_order"])

    async def test_direct_order_uses_longest_matching_menu_result(self) -> None:
        from graph.graph import order_browser_agent_node

        state = {
            "messages": [
                HumanMessage(
                    content="황금올리브치킨™핫크리스피 (한마리)를 배달 주문 준비해줘"
                )
            ],
            "selected_order": None,
            "menu_results": {
                "황금올리브치킨 핫크리스피 주문": [
                    {
                        "name": "황금올리브치킨™",
                        "category": "후라이드",
                        "price": 23000,
                    },
                    {
                        "name": "황금올리브치킨™핫크리스피",
                        "category": "후라이드",
                        "price": 24000,
                    },
                ]
            },
            "cs_results": {},
        }

        with patch("graph.graph.prepare_bbq_order.func") as mock_prepare, patch(
            "graph.graph._order_agent"
        ) as mock_order_agent:
            mock_prepare.return_value = json.dumps(
                {"ok": True, "result": "핫크리스피 주문 준비를 이어갑니다."},
                ensure_ascii=False,
            )
            mock_order_agent.ainvoke = AsyncMock()

            result = await order_browser_agent_node(state)

        mock_order_agent.ainvoke.assert_not_called()
        mock_prepare.assert_called_once_with(
            "황금올리브치킨™핫크리스피",
            ["한마리"],
            "delivery",
            state,
            menu_category="후라이드",
        )
        self.assertEqual(
            result["response"],
            {"type": "text", "message": "핫크리스피 주문 준비를 이어갑니다."},
        )
        self.assertIsNone(result["selected_order"])

    async def test_direct_order_asks_clarification_when_menu_result_is_ambiguous(
        self,
    ) -> None:
        from graph.graph import order_browser_agent_node

        state = {
            "messages": [HumanMessage(content="황금올리브 주문 준비해줘")],
            "selected_order": None,
            "menu_results": {
                "황금올리브치킨 주문": [
                    {"name": "황금올리브치킨™", "category": "후라이드", "price": 23000},
                    {
                        "name": "황금올리브치킨™핫크리스피",
                        "category": "후라이드",
                        "price": 24000,
                    },
                ]
            },
            "cs_results": {},
        }

        with patch("graph.graph.prepare_bbq_order.func") as mock_prepare, patch(
            "graph.graph._order_agent"
        ) as mock_order_agent:
            mock_order_agent.ainvoke = AsyncMock()

            result = await order_browser_agent_node(state)

        mock_prepare.assert_not_called()
        mock_order_agent.ainvoke.assert_not_called()
        self.assertEqual(result["response"]["type"], "clarification")
        self.assertIn("어떤 메뉴", result["response"]["message"])

    async def test_direct_order_without_menu_results_does_not_guess_with_llm(
        self,
    ) -> None:
        from graph.graph import order_browser_agent_node

        state = {
            "messages": [HumanMessage(content="핫크리스피 주문 준비해줘")],
            "selected_order": None,
            "menu_results": {},
            "cs_results": {},
        }

        with patch("graph.graph.prepare_bbq_order.func") as mock_prepare, patch(
            "graph.graph._order_agent"
        ) as mock_order_agent:
            mock_order_agent.ainvoke = AsyncMock()

            result = await order_browser_agent_node(state)

        mock_prepare.assert_not_called()
        mock_order_agent.ainvoke.assert_not_called()
        self.assertEqual(result["response"]["type"], "clarification")
        self.assertIn("정확한 메뉴명", result["response"]["message"])


if __name__ == "__main__":
    unittest.main()
