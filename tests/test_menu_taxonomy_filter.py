import json
import unittest
from unittest.mock import MagicMock, patch

from vectorstore.build_menu_index import (
    build_metadata,
    derive_product_family,
    derive_product_type,
)


def make_doc(
    name,
    category,
    product_family,
    spiciness="매움",
    *,
    product_type="main_menu",
    primary_texture="바삭함",
    cooking_method="fried",
    sauce_style="none",
    option_tags="",
):
    return type(
        "Doc",
        (),
        {
            "page_content": f"{name} 설명",
            "metadata": {
                "name": name,
                "category": category,
                "price": 25000,
                "spiciness": spiciness,
                "texture": "바삭함",
                "primary_texture": primary_texture,
                "product_type": product_type,
                "product_family": product_family,
                "cooking_method": cooking_method,
                "sauce_style": sauce_style,
                "option_tags": option_tags,
                "imageURL": "https://example.com/menu.png",
            },
        },
    )()


class ProductFamilyMetadataTests(unittest.TestCase):
    def test_derive_product_family_maps_main_chicken_category(self):
        self.assertEqual(
            derive_product_family({"구분": "양념", "메뉴명": "황금올리브치킨™매운양념"}),
            "chicken",
        )

    def test_derive_product_family_maps_burger_category(self):
        self.assertEqual(
            derive_product_family(
                {"구분": "피자&버거", "메뉴명": "BBQ 썬더 치킨버거 스파이시"}
            ),
            "burger",
        )

    def test_derive_product_family_infers_new_menu_side(self):
        self.assertEqual(
            derive_product_family({"구분": "신메뉴", "메뉴명": "뿜치킹 감자튀김"}),
            "side",
        )

    def test_derive_product_type_maps_main_chicken_category(self):
        self.assertEqual(
            derive_product_type({"구분": "후라이드", "메뉴명": "황금올리브치킨™"}),
            "main_menu",
        )

    def test_derive_product_type_maps_sauce_category(self):
        self.assertEqual(
            derive_product_type({"구분": "소스&시즈닝&무", "메뉴명": "BBQ양념치킨컵소스(40g)"}),
            "sauce",
        )

    def test_derive_product_type_infers_new_menu_main_before_unknown(self):
        self.assertEqual(
            derive_product_type({"구분": "신메뉴", "메뉴명": "뿜치킹"}),
            "main_menu",
        )

    def test_build_metadata_includes_normalized_taxonomy_fields(self):
        metadata = build_metadata({"구분": "후라이드", "메뉴명": "황금올리브치킨™핫크리스피"})

        self.assertEqual(metadata["product_type"], "main_menu")
        self.assertEqual(metadata["product_family"], "chicken")
        self.assertEqual(metadata["cooking_method"], "fried")

    def test_build_metadata_marks_sauce_traits_not_applicable(self):
        metadata = build_metadata(
            {
                "구분": "소스&시즈닝&무",
                "메뉴명": "BBQ양념치킨컵소스(40g)",
                "texture": "부드러움",
                "spiciness": "순함",
            }
        )

        self.assertEqual(metadata["product_type"], "sauce")
        self.assertEqual(metadata["product_family"], "sauce")
        self.assertEqual(metadata["texture"], "")
        self.assertEqual(metadata["spiciness"], "")
        self.assertEqual(metadata["primary_texture"], "")

    def test_build_metadata_separates_sauced_chicken_from_primary_crispiness(self):
        metadata = build_metadata(
            {
                "구분": "양념",
                "메뉴명": "황금올리브치킨™양념",
                "texture": "바삭함",
                "spiciness": "순함",
            }
        )

        self.assertEqual(metadata["product_type"], "main_menu")
        self.assertEqual(metadata["product_family"], "chicken")
        self.assertEqual(metadata["cooking_method"], "fried")
        self.assertEqual(metadata["sauce_style"], "sauced")
        self.assertEqual(metadata["primary_texture"], "촉촉함")

    def test_build_metadata_extracts_option_tags(self):
        metadata = build_metadata(
            {
                "구분": "후라이드",
                "메뉴명": "황금올리브치킨™",
                "구매 옵션": '[{"items":[{"name":"순살 변경"},{"name":"닭다리 변경"}]}]',
            }
        )

        self.assertIn("순살", metadata["option_tags"])
        self.assertIn("닭다리", metadata["option_tags"])

    def test_build_metadata_does_not_classify_main_dish_from_add_on_options(self):
        metadata = build_metadata(
            {
                "구분": "후라이드",
                "메뉴명": "황금올리브치킨™",
                "설명": "겉은 바삭 육즙 가득한 부드러운 속살",
                "texture": "바삭함",
                "spiciness": "순함",
                "구매 옵션": '[{"items":[{"name":"스모크소스(12g)"},{"name":"볼케이노 핫소스(150g)"}]}]',
            }
        )

        self.assertEqual(metadata["cooking_method"], "fried")
        self.assertEqual(metadata["sauce_style"], "none")
        self.assertEqual(metadata["primary_texture"], "바삭함")


class QueryFamilyInferenceTests(unittest.TestCase):
    def test_infer_requested_family_treats_chicken_as_chicken(self):
        from tools.search_menu import infer_requested_family

        self.assertEqual(infer_requested_family("매운 치킨 추천해줘"), "chicken")

    def test_infer_requested_family_treats_chicken_burger_as_burger_pizza(self):
        from tools.search_menu import infer_requested_family

        self.assertEqual(infer_requested_family("치킨버거 추천해줘"), "burger_pizza")

    def test_infer_requested_family_returns_none_for_generic_recommendation(self):
        from tools.search_menu import infer_requested_family

        self.assertIsNone(infer_requested_family("맛있는 메뉴 추천해줘"))


class SearchMenuTaxonomyFilterTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("tools.search_menu.build_redis_cache", return_value=None)
        self.addCleanup(patcher.stop)
        patcher.start()

    @patch("tools.search_menu._get_retriever")
    def test_chicken_query_excludes_burger_pizza_results(self, mock_get_retriever):
        from tools.search_menu import search_menu

        mock_get_retriever.return_value.invoke.return_value = [
            make_doc(
                "BBQ 썬더 치킨버거 스파이시",
                "피자&버거",
                "burger",
                product_type="main_menu",
            ),
            make_doc("황금올리브치킨™핫크리스피", "후라이드", "chicken"),
        ]

        payload = json.loads(search_menu.func("매운 치킨 추천해줘", {"menu_results": {}}))

        self.assertEqual(
            [item["name"] for item in payload["results"]], ["황금올리브치킨™핫크리스피"]
        )

    @patch("tools.search_menu._get_retriever")
    def test_burger_query_keeps_burger_pizza_results(self, mock_get_retriever):
        from tools.search_menu import search_menu

        mock_get_retriever.return_value.invoke.return_value = [
            make_doc(
                "BBQ 썬더 치킨버거 스파이시",
                "피자&버거",
                "burger",
                product_type="main_menu",
            ),
            make_doc("황금올리브치킨™핫크리스피", "후라이드", "chicken"),
        ]

        payload = json.loads(search_menu.func("치킨버거 추천해줘", {"menu_results": {}}))

        self.assertEqual(
            [item["name"] for item in payload["results"]],
            ["BBQ 썬더 치킨버거 스파이시"],
        )

    @patch("tools.search_menu._get_retriever")
    def test_missing_product_family_defaults_to_unknown_without_crashing(
        self, mock_get_retriever
    ):
        from tools.search_menu import search_menu

        doc = make_doc("임시 치킨", "신메뉴", "chicken")
        del doc.metadata["product_family"]
        mock_get_retriever.return_value.invoke.return_value = [doc]

        payload = json.loads(search_menu.func("매운 치킨 추천해줘", {"menu_results": {}}))

        self.assertEqual(payload["results"][0]["product_family"], "unknown")


class SearchMenuRetrievalRoutingTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("tools.search_menu.build_redis_cache", return_value=None)
        self.addCleanup(patcher.stop)
        patcher.start()

    @patch(
        "tools.search_menu.rerank_menu_items",
        side_effect=lambda _query, results: results,
    )
    @patch("tools.search_menu.detect_recommendation_criteria", return_value=None)
    @patch("tools.search_menu._get_retriever")
    def test_simple_family_query_uses_rule_filter_fast_path(
        self,
        mock_get_retriever,
        _mock_detect_recommendation_criteria,
        _mock_rerank_menu_items,
    ):
        from tools.search_menu import search_menu

        retriever = MagicMock()
        retriever.vectorstore.similarity_search.return_value = [
            make_doc("황금올리브치킨™핫크리스피", "후라이드", "chicken")
        ]
        mock_get_retriever.return_value = retriever

        payload = json.loads(search_menu.func("치킨 추천해줘", {"menu_results": {}}))

        retriever.vectorstore.similarity_search.assert_called_once_with(
            "치킨 추천해줘",
            k=5,
            filter={"product_family": {"$eq": "chicken"}},
        )
        retriever.invoke.assert_not_called()
        self.assertEqual(
            [item["name"] for item in payload["results"]],
            ["황금올리브치킨™핫크리스피"],
        )

    @patch(
        "tools.search_menu.rerank_menu_items",
        side_effect=lambda _query, results: results,
    )
    @patch("tools.search_menu.detect_recommendation_criteria", return_value=None)
    @patch("tools.search_menu._get_retriever")
    def test_single_spiciness_query_uses_rule_filter(
        self,
        mock_get_retriever,
        _mock_detect_recommendation_criteria,
        _mock_rerank_menu_items,
    ):
        from tools.search_menu import search_menu

        retriever = MagicMock()
        retriever.vectorstore.similarity_search.return_value = [
            make_doc("황금올리브치킨™핫크리스피", "후라이드", "chicken")
        ]
        mock_get_retriever.return_value = retriever

        payload = json.loads(search_menu.func("매운 치킨 추천해줘", {"menu_results": {}}))

        retriever.vectorstore.similarity_search.assert_called_once_with(
            "매운 치킨 추천해줘",
            k=5,
            filter={
                "$and": [
                    {"spiciness": {"$eq": "매움"}},
                    {"product_family": {"$eq": "chicken"}},
                ]
            },
        )
        retriever.invoke.assert_not_called()
        self.assertEqual(
            [item["name"] for item in payload["results"]],
            ["황금올리브치킨™핫크리스피"],
        )

    @patch(
        "tools.search_menu.rerank_menu_items",
        side_effect=lambda _query, results: results,
    )
    @patch("tools.search_menu.detect_recommendation_criteria", return_value=None)
    @patch("tools.search_menu._get_retriever")
    def test_price_query_uses_rule_filter(
        self,
        mock_get_retriever,
        _mock_detect_recommendation_criteria,
        _mock_rerank_menu_items,
    ):
        from tools.search_menu import search_menu

        retriever = MagicMock()
        retriever.vectorstore.similarity_search.return_value = [
            make_doc("황금올리브치킨 반마리", "1인분 메뉴", "chicken")
        ]
        mock_get_retriever.return_value = retriever

        payload = json.loads(
            search_menu.func("2만원 이하 치킨 추천해줘", {"menu_results": {}})
        )

        retriever.vectorstore.similarity_search.assert_called_once_with(
            "2만원 이하 치킨 추천해줘",
            k=5,
            filter={
                "$and": [
                    {"price": {"$lte": 20000}},
                    {"product_family": {"$eq": "chicken"}},
                ]
            },
        )
        retriever.invoke.assert_not_called()
        self.assertEqual(
            [item["name"] for item in payload["results"]],
            ["황금올리브치킨 반마리"],
        )

    @patch(
        "tools.search_menu.rerank_menu_items",
        side_effect=lambda _query, results: results,
    )
    @patch("tools.search_menu.detect_recommendation_criteria", return_value=None)
    @patch("tools.search_menu._get_retriever")
    def test_fast_path_falls_back_to_self_query_when_family_filter_removes_results(
        self,
        mock_get_retriever,
        _mock_detect_recommendation_criteria,
        _mock_rerank_menu_items,
    ):
        from tools.search_menu import search_menu

        retriever = MagicMock()
        retriever.vectorstore.similarity_search.return_value = [
            make_doc(
                "BBQ 썬더 치킨버거 스파이시",
                "피자&버거",
                "burger",
                product_type="main_menu",
            )
        ]
        retriever.invoke.return_value = [
            make_doc("황금올리브치킨™핫크리스피", "후라이드", "chicken")
        ]
        mock_get_retriever.return_value = retriever

        payload = json.loads(search_menu.func("치킨 추천해줘", {"menu_results": {}}))

        retriever.vectorstore.similarity_search.assert_called_once()
        retriever.invoke.assert_called_once_with("치킨 추천해줘")
        self.assertEqual(
            [item["name"] for item in payload["results"]],
            ["황금올리브치킨™핫크리스피"],
        )

    @patch(
        "tools.search_menu.rerank_menu_items",
        side_effect=lambda _query, results: results,
    )
    @patch("tools.search_menu.detect_recommendation_criteria", return_value=None)
    @patch("tools.search_menu._get_retriever")
    def test_structured_query_does_not_retry_self_query_when_empty(
        self,
        mock_get_retriever,
        _mock_detect_recommendation_criteria,
        _mock_rerank_menu_items,
    ):
        from tools.search_menu import search_menu

        retriever = MagicMock()
        retriever.invoke.return_value = []
        mock_get_retriever.return_value = retriever

        payload = json.loads(
            search_menu.func("2만원 이하 치킨 추천해줘", {"menu_results": {}})
        )

        retriever.invoke.assert_called_once_with("2만원 이하 치킨 추천해줘")
        self.assertEqual(payload["results"], [])


class FinalAnswerTaxonomyTests(unittest.TestCase):
    def test_format_menu_cards_preserves_product_family(self):
        from tools.final_answer import format_menu_cards

        payload = format_menu_cards(
            [
                {
                    "name": "황금올리브치킨™핫크리스피",
                    "category": "후라이드",
                    "price": 24000,
                    "description": "매운 치킨",
                    "product_type": "main_menu",
                    "product_family": "chicken",
                }
            ]
        )

        self.assertEqual(payload["items"][0]["product_type"], "main_menu")
        self.assertEqual(payload["items"][0]["product_family"], "chicken")


if __name__ == "__main__":
    unittest.main()
