import json
import unittest
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

from graph.graph import MENU_SYSTEM_PROMPT, _menu_tools, menu_agent_node
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from tools.final_answer import final_answer_menu
from tools.search_menu import search_menu
from vectorstore import build_menu_index
from vectorstore.build_menu_index import build_metadata


class MenuImageURLTests(unittest.TestCase):
    def test_menu_agent_tools_include_final_answer_menu(self) -> None:
        self.assertIn("final_answer_menu", [tool.name for tool in _menu_tools])

    def test_menu_prompt_instructs_final_answer_menu(self) -> None:
        self.assertIn("final_answer_menu", MENU_SYSTEM_PROMPT)

    def test_build_metadata_includes_image_url(self) -> None:
        metadata = build_metadata(
            {"메뉴명": "뿜치킹", "imageURL": "https://example.com/menu.png"}
        )

        self.assertEqual(metadata["imageURL"], "https://example.com/menu.png")

    def test_final_answer_menu_preserves_image_url(self) -> None:
        payload = json.loads(
            final_answer_menu.invoke(
                {
                    "items": [
                        {
                            "name": "뿜치킹",
                            "category": "신메뉴",
                            "price": 25000,
                            "description": "치즈 풍미",
                            "imageURL": "https://example.com/menu.png",
                        }
                    ]
                }
            )
        )

        self.assertEqual(
            payload["items"][0]["imageURL"], "https://example.com/menu.png"
        )

    @patch("tools.search_menu._get_retriever")
    def test_search_menu_includes_image_url(self, mock_get_retriever) -> None:
        mock_doc = type(
            "Doc",
            (),
            {
                "page_content": "치즈 풍미",
                "metadata": {
                    "name": "뿜치킹",
                    "category": "신메뉴",
                    "price": 25000,
                    "imageURL": "https://example.com/menu.png",
                },
            },
        )()
        mock_get_retriever.return_value.invoke.return_value = [mock_doc]

        payload = json.loads(search_menu.func("치킨", {"menu_results": {}}))

        self.assertEqual(
            payload["results"][0]["imageURL"], "https://example.com/menu.png"
        )

    @patch("vectorstore.build_menu_index._clear_existing_collection", create=True)
    @patch("vectorstore.build_menu_index.Chroma.from_documents")
    @patch("vectorstore.build_menu_index.OpenAIEmbeddings")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='[{"메뉴명":"뿜치킹","가격":25000,"imageURL":"https://example.com/menu.png"}]',
    )
    def test_build_index_clears_existing_collection_before_rebuild(
        self,
        _mock_open,
        mock_embeddings,
        mock_from_documents,
        mock_clear_existing_collection,
    ) -> None:
        mock_vectorstore = MagicMock()
        mock_vectorstore._collection.count.return_value = 1
        mock_from_documents.return_value = mock_vectorstore

        build_menu_index.build_index()

        mock_clear_existing_collection.assert_called_once_with(
            build_menu_index.CHROMA_PATH,
            build_menu_index.COLLECTION_NAME,
        )


class MenuAgentResponseTests(unittest.IsolatedAsyncioTestCase):
    @patch("graph.graph._menu_agent")
    async def test_menu_agent_node_falls_back_to_menu_cards_from_search_results(
        self, mock_menu_agent
    ) -> None:
        mock_menu_agent.ainvoke = AsyncMock(
            return_value={
                "messages": [
                    HumanMessage(content="추천해줘"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "search_menu",
                                "args": {"query": "추천해줘"},
                                "id": "call_1",
                                "type": "tool_call",
                            }
                        ],
                    ),
                    ToolMessage(
                        content=json.dumps(
                            {
                                "results": [
                                    {
                                        "name": "뿜치킹",
                                        "category": "신메뉴",
                                        "price": 25000,
                                        "description": "치즈 풍미",
                                        "imageURL": "https://example.com/menu.png",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        ),
                        name="search_menu",
                        tool_call_id="call_1",
                    ),
                ]
            }
        )

        result = await menu_agent_node(
            {
                "messages": [HumanMessage(content="추천해줘")],
                "intent": "menu",
                "response": {},
                "menu_results": {},
                "cs_results": {},
            }
        )

        self.assertEqual(result["response"]["type"], "menu_cards")
        self.assertEqual(
            result["response"]["items"][0]["imageURL"], "https://example.com/menu.png"
        )

    @patch("graph.graph._menu_agent")
    async def test_menu_agent_node_prefers_search_results_over_llm_menu_cards(
        self, mock_menu_agent
    ) -> None:
        full_options = (
            '[{"group_name":"음료 선택","required_select_count":1,'
            '"max_select_count":1,"items":[{"name":"콜라","add_price":0}]}]'
        )
        truncated_options = '[{"group_name":"음료 선택"...}]'
        search_results = [
            {
                "name": "황금올리브치킨 반마리 세트",
                "category": "세트메뉴",
                "price": 18500,
                "description": "세트",
                "options": full_options,
            }
        ]

        mock_menu_agent.ainvoke = AsyncMock(
            return_value={
                "messages": [
                    HumanMessage(content="반마리 세트 추천해줘"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "search_menu",
                                "args": {"query": "반마리 세트 추천해줘"},
                                "id": "call_1",
                                "type": "tool_call",
                            }
                        ],
                    ),
                    ToolMessage(
                        content=json.dumps(
                            {"results": search_results},
                            ensure_ascii=False,
                        ),
                        name="search_menu",
                        tool_call_id="call_1",
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "final_answer_menu",
                                "args": {"items": search_results},
                                "id": "call_2",
                                "type": "tool_call",
                            }
                        ],
                    ),
                    ToolMessage(
                        content=json.dumps(
                            {
                                "type": "menu_cards",
                                "items": [
                                    {
                                        **search_results[0],
                                        "options": truncated_options,
                                    }
                                ],
                            },
                            ensure_ascii=False,
                        ),
                        name="final_answer_menu",
                        tool_call_id="call_2",
                    ),
                ]
            }
        )

        result = await menu_agent_node(
            {
                "messages": [HumanMessage(content="반마리 세트 추천해줘")],
                "intent": "menu",
                "response": {},
                "menu_results": {},
                "cs_results": {},
            }
        )

        self.assertEqual(result["response"]["type"], "menu_cards")
        self.assertEqual(result["response"]["items"][0]["options"], full_options)


if __name__ == "__main__":
    unittest.main()
