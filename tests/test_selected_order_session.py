import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from langchain_core.messages import HumanMessage

from api.services.session import SessionRecord


def make_session() -> SessionRecord:
    return SessionRecord(id="sess_test", created_at=datetime.now(timezone.utc))


class SelectedOrderSessionTests(unittest.IsolatedAsyncioTestCase):
    def test_user_message_can_store_selected_order_for_next_response(self) -> None:
        from api.services.message import MessageService

        selected_order = {
            "menu_name": "황금올리브치킨",
            "options": ["콜라 1.25L"],
            "order_type": "delivery",
        }
        session = make_session()

        MessageService().add_user_message(
            session,
            "황금올리브치킨 주문 준비",
            selected_order=selected_order,
        )

        self.assertEqual(session.selected_order, selected_order)

    def test_selected_order_schema_accepts_option_details(self) -> None:
        from api.schemas import SelectedOrderIn

        selected_order = SelectedOrderIn(
            menu_name="Golden Olive",
            menu_category="Fried",
            options=["Coke 1.25L"],
            option_details=[
                {
                    "group_name": "Drink selection",
                    "option_name": "Coke 1.25L",
                    "add_price": 1500,
                    "required": True,
                }
            ],
            order_type="delivery",
        )

        self.assertEqual(
            selected_order.model_dump()["option_details"][0]["option_name"],
            "Coke 1.25L",
        )

    def test_assistant_order_status_is_stored_as_structured_item(self) -> None:
        from api.services.message import MessageService

        session = make_session()
        response = {
            "type": "order_status",
            "status": "cart_ready",
            "message": "Cart is ready.",
            "menu_name": "Golden Olive",
            "expected_options": ["Coke 1.25L"],
            "order_type": "delivery",
            "current_url": "https://www.bbq.co.kr/order/cart",
            "next_action": "Review the cart in the open BBQ browser.",
        }

        api_message = MessageService().store_assistant_response(
            session, response, "menu"
        )

        self.assertEqual(api_message["type"], "order_status")
        self.assertEqual(api_message["content"], "Cart is ready.")
        self.assertEqual(api_message["items"], [response])

    async def test_response_service_passes_and_clears_selected_order(self) -> None:
        from api.services.response import ResponseService

        selected_order = {
            "menu_name": "황금올리브치킨",
            "options": ["콜라 1.25L"],
            "order_type": "delivery",
        }
        session = make_session()
        session.lc_messages.append(HumanMessage(content="주문 준비"))
        session.selected_order = selected_order
        session.last_menu_query = "매운 치킨 추천해줘"
        session.shown_menu_names = ["뿜치킹"]

        class FakeGraph:
            async def ainvoke(self, state):
                self.state = state
                return {
                    "messages": state["messages"],
                    "intent": "menu",
                    "response": {"type": "text", "message": "ok"},
                    "menu_results": {},
                    "cs_results": {},
                    "selected_order": None,
                    "last_menu_query": "매운 치킨 추천해줘",
                    "shown_menu_names": ["뿜치킹", "스모크치킨"],
                }

        fake_graph = FakeGraph()

        with patch("graph.graph.graph", fake_graph):
            response, intent = await ResponseService().generate(session)

        self.assertEqual(fake_graph.state["selected_order"], selected_order)
        self.assertEqual(fake_graph.state["last_menu_query"], "매운 치킨 추천해줘")
        self.assertEqual(fake_graph.state["shown_menu_names"], ["뿜치킹"])
        self.assertEqual(session.last_menu_query, "매운 치킨 추천해줘")
        self.assertEqual(session.shown_menu_names, ["뿜치킹", "스모크치킨"])
        self.assertIsNone(session.selected_order)
        self.assertEqual(response["message"], "ok")
        self.assertEqual(intent, "menu")


if __name__ == "__main__":
    unittest.main()
