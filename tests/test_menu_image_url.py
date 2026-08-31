import unittest
from unittest.mock import MagicMock, mock_open, patch

from graph.graph import menu_agent_node
from langchain_core.messages import HumanMessage
from tools.final_answer import format_menu_cards
from tools.search_menu import search_menu
from vectorstore import build_menu_index
from vectorstore.build_menu_index import build_metadata


class MenuImageURLTests(unittest.TestCase):
    def test_build_metadata_includes_image_url(self) -> None:
        metadata = build_metadata(
            {"메뉴명": "뿜치킹", "imageURL": "https://example.com/menu.png"}
        )

        self.assertEqual(metadata["imageURL"], "https://example.com/menu.png")

    def test_format_menu_cards_preserves_image_url(self) -> None:
        payload = format_menu_cards(
            [
                {
                    "name": "뿜치킹",
                    "category": "신메뉴",
                    "price": 25000,
                    "description": "치즈 풍미",
                    "imageURL": "https://example.com/menu.png",
                }
            ]
        )

        self.assertEqual(
            payload["items"][0]["imageURL"], "https://example.com/menu.png"
        )

    @patch("tools.search_menu.build_criteria_retrieval_query", side_effect=lambda q: q)
    @patch("tools.search_menu.detect_recommendation_criteria", return_value=None)
    @patch("tools.search_menu.rerank_menu_items", side_effect=lambda _query, results: results)
    @patch("tools.search_menu._get_retriever")
    def test_search_menu_includes_image_url(
        self,
        mock_get_retriever,
        _mock_rerank_menu_items,
        _mock_detect_recommendation_criteria,
        _mock_build_criteria_retrieval_query,
    ) -> None:
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

        payload = search_menu.func("치킨", {"menu_results": {}})

        self.assertIn("https://example.com/menu.png", payload)

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
        _mock_embeddings,
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
    @patch("graph.graph.search_menu_results")
    async def test_menu_agent_node_returns_menu_cards_from_direct_search(
        self, mock_search_menu_results
    ) -> None:
        mock_search_menu_results.return_value = [
            {
                "name": "뿜치킹",
                "category": "신메뉴",
                "price": 25000,
                "description": "치즈 풍미",
                "imageURL": "https://example.com/menu.png",
            }
        ]

        result = await menu_agent_node(
            {
                "messages": [HumanMessage(content="추천해줘")],
                "intent": "menu",
                "response": {},
                "menu_results": {},
                "cs_results": {},
            }
        )

        mock_search_menu_results.assert_called_once()
        self.assertEqual(result["response"]["type"], "menu_cards")
        self.assertEqual(
            result["response"]["items"][0]["imageURL"],
            "https://example.com/menu.png",
        )
        self.assertEqual(
            result["menu_results"]["추천해줘"][0]["imageURL"],
            "https://example.com/menu.png",
        )
        self.assertEqual(result["last_menu_query"], "추천해줘")
        self.assertEqual(result["shown_menu_names"], ["뿜치킹"])

    @patch("graph.graph.search_menu_results")
    async def test_menu_agent_node_preserves_full_search_result_options(
        self, mock_search_menu_results
    ) -> None:
        full_options = (
            '[{"group_name":"음료 선택","required_select_count":1,'
            '"max_select_count":1,"items":[{"name":"콜라","add_price":0}]}]'
        )
        search_results = [
            {
                "name": "황금올리브치킨 반마리 세트",
                "category": "세트메뉴",
                "price": 18500,
                "description": "세트",
                "options": full_options,
            }
        ]
        mock_search_menu_results.return_value = search_results

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

    @patch("graph.graph.search_menu_results")
    async def test_menu_agent_node_returns_text_when_no_menu_results(
        self, mock_search_menu_results
    ) -> None:
        mock_search_menu_results.return_value = []

        result = await menu_agent_node(
            {
                "messages": [HumanMessage(content="추천해줘")],
                "intent": "menu",
                "response": {},
                "menu_results": {},
                "cs_results": {},
            }
        )

        self.assertEqual(result["response"]["type"], "text")
        self.assertNotIn("menu_results", result)


if __name__ == "__main__":
    unittest.main()
