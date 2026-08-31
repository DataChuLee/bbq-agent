import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
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
            response, intent, sources = await ResponseService().generate(session)

        self.assertEqual(fake_graph.state["selected_order"], selected_order)
        self.assertEqual(fake_graph.state["last_menu_query"], "매운 치킨 추천해줘")
        self.assertEqual(fake_graph.state["shown_menu_names"], ["뿜치킹"])
        self.assertEqual(session.last_menu_query, "매운 치킨 추천해줘")
        self.assertEqual(session.shown_menu_names, ["뿜치킹", "스모크치킨"])
        self.assertIsNone(session.selected_order)
        self.assertEqual(response["message"], "ok")
        self.assertEqual(intent, "menu")
        self.assertEqual(sources, [])

    async def test_response_service_returns_cs_sources(self) -> None:
        from api.services.response import ResponseService

        session = make_session()
        session.lc_messages.append(HumanMessage(content="환불 문의"))

        class FakeGraph:
            async def ainvoke(self, state):
                return {
                    "messages": state["messages"],
                    "intent": "cs",
                    "response": {"type": "text", "message": "고객센터 안내"},
                    "menu_results": {},
                    "cs_results": {
                        "환불 문의": [
                            {
                                "content": "환불 접수 방법",
                                "cs_category": "환불",
                                "claim_category": "결제",
                            }
                        ]
                    },
                    "last_cs_query": "환불 문의",
                }

        with patch("graph.graph.graph", FakeGraph()):
            response, intent, sources = await ResponseService().generate(session)

        self.assertEqual(response["message"], "고객센터 안내")
        self.assertEqual(intent, "cs")
        self.assertEqual(
            sources,
            [
                {
                    "source_type": "cs",
                    "content": "환불 접수 방법",
                    "score": None,
                    "metadata": {
                        "cs_category": "환불",
                        "claim_category": "결제",
                    },
                }
            ],
        )

    async def test_response_service_does_not_stream_menu_agent_internal_tokens(
        self,
    ) -> None:
        from api.services.response import ResponseService

        session = make_session()
        session.lc_messages.append(HumanMessage(content="매운 치킨을 추천해줘"))

        class FakeGraph:
            async def astream_events(self, state, version):
                yield {
                    "event": "on_chat_model_stream",
                    "metadata": {"langgraph_node": "menu_agent"},
                    "data": {"chunk": SimpleNamespace(content='{"query": "치킨"}')},
                }
                yield {
                    "event": "on_chain_end",
                    "name": "LangGraph",
                    "data": {
                        "output": {
                            "messages": state["messages"],
                            "intent": "menu",
                            "response": {"type": "menu_cards", "items": []},
                        }
                    },
                }

        with patch("graph.graph.graph", FakeGraph()):
            events = [item async for item in ResponseService().generate_stream(session)]

        self.assertNotIn(("token", '{"query": "치킨"}'), events)
        self.assertEqual(
            events[-1],
            ("done", {"type": "menu_cards", "items": []}, "menu", []),
        )


if __name__ == "__main__":
    unittest.main()
