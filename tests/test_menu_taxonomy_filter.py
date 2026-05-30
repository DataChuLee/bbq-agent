import json
import unittest
from unittest.mock import patch

from vectorstore.build_menu_index import build_metadata, derive_product_family


def make_doc(name, category, product_family, spiciness="매움"):
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
                "product_family": product_family,
                "imageURL": "https://example.com/menu.png",
            },
        },
    )()


class ProductFamilyMetadataTests(unittest.TestCase):
    def test_derive_product_family_maps_main_chicken_category(self):
        self.assertEqual(
            derive_product_family({"구분": "양념", "메뉴명": "황금올리브치킨™매운양념"}),
            "main_chicken",
        )

    def test_derive_product_family_maps_burger_category(self):
        self.assertEqual(
            derive_product_family(
                {"구분": "피자&버거", "메뉴명": "BBQ 썬더 치킨버거 스파이시"}
            ),
            "burger_pizza",
        )

    def test_derive_product_family_infers_new_menu_side(self):
        self.assertEqual(
            derive_product_family({"구분": "신메뉴", "메뉴명": "뿜치킹 감자튀김"}),
            "side",
        )

    def test_build_metadata_includes_product_family(self):
        metadata = build_metadata({"구분": "후라이드", "메뉴명": "황금올리브치킨™핫크리스피"})

        self.assertEqual(metadata["product_family"], "main_chicken")


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
    @patch("tools.search_menu._get_retriever")
    def test_chicken_query_excludes_burger_pizza_results(self, mock_get_retriever):
        from tools.search_menu import search_menu

        mock_get_retriever.return_value.invoke.return_value = [
            make_doc("BBQ 썬더 치킨버거 스파이시", "피자&버거", "burger_pizza"),
            make_doc("황금올리브치킨™핫크리스피", "후라이드", "main_chicken"),
        ]

        payload = json.loads(search_menu.func("매운 치킨 추천해줘", {"menu_results": {}}))

        self.assertEqual(
            [item["name"] for item in payload["results"]], ["황금올리브치킨™핫크리스피"]
        )

    @patch("tools.search_menu._get_retriever")
    def test_burger_query_keeps_burger_pizza_results(self, mock_get_retriever):
        from tools.search_menu import search_menu

        mock_get_retriever.return_value.invoke.return_value = [
            make_doc("BBQ 썬더 치킨버거 스파이시", "피자&버거", "burger_pizza"),
            make_doc("황금올리브치킨™핫크리스피", "후라이드", "main_chicken"),
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

        doc = make_doc("임시 치킨", "신메뉴", "main_chicken")
        del doc.metadata["product_family"]
        mock_get_retriever.return_value.invoke.return_value = [doc]

        payload = json.loads(search_menu.func("매운 치킨 추천해줘", {"menu_results": {}}))

        self.assertEqual(payload["results"][0]["product_family"], "unknown")


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
                    "product_family": "main_chicken",
                }
            ]
        )

        self.assertEqual(payload["items"][0]["product_family"], "main_chicken")


if __name__ == "__main__":
    unittest.main()
