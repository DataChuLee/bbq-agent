import json
import unittest
from unittest.mock import patch


def make_item(
    name,
    *,
    texture="",
    spiciness="",
    category="후라이드",
    product_type="main_menu",
    product_family="chicken",
    primary_texture="",
    cooking_method="",
    sauce_style="none",
    option_tags="",
    description="",
):
    return {
        "name": name,
        "category": category,
        "price": 23000,
        "texture": texture,
        "spiciness": spiciness,
        "primary_texture": primary_texture or texture,
        "product_type": product_type,
        "description": description,
        "product_family": product_family,
        "cooking_method": cooking_method,
        "sauce_style": sauce_style,
        "option_tags": option_tags,
    }


def make_doc(
    name,
    *,
    texture="",
    spiciness="",
    product_type="main_menu",
    product_family="chicken",
    primary_texture="",
    cooking_method="",
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
                "category": "후라이드",
                "price": 23000,
                "texture": texture,
                "spiciness": spiciness,
                "primary_texture": primary_texture or texture,
                "product_type": product_type,
                "product_family": product_family,
                "cooking_method": cooking_method,
                "sauce_style": sauce_style,
                "option_tags": option_tags,
            },
        },
    )()


class RecommendationCriteriaDetectionTests(unittest.TestCase):
    def test_detects_beer_pairing_intent(self):
        from tools.recommendation_criteria import detect_recommendation_criteria

        criteria = detect_recommendation_criteria("맥주랑 어울리는 치킨 추천해줘")

        self.assertIsNotNone(criteria)
        self.assertEqual(criteria["intent"], "beer_pairing")

    def test_detects_kids_friendly_intent(self):
        from tools.recommendation_criteria import detect_recommendation_criteria

        criteria = detect_recommendation_criteria("아이랑 먹기 좋은 치킨 추천해줘")

        self.assertIsNotNone(criteria)
        self.assertEqual(criteria["intent"], "kids_friendly")

    def test_detects_solo_meal_intent(self):
        from tools.recommendation_criteria import detect_recommendation_criteria

        criteria = detect_recommendation_criteria("혼자 먹을 메뉴 추천해줘")

        self.assertIsNotNone(criteria)
        self.assertEqual(criteria["intent"], "solo_meal")

    def test_returns_none_for_direct_menu_attribute_query(self):
        from tools.recommendation_criteria import detect_recommendation_criteria

        self.assertIsNone(detect_recommendation_criteria("매운 치킨 추천해줘"))


class CriteriaAwareRerankingTests(unittest.TestCase):
    def test_beer_pairing_ranks_crispy_spicy_chicken_first(self):
        from tools.recommendation_criteria import rerank_menu_items

        items = [
            make_item(
                "순한 부드러운 치킨",
                texture="부드러움",
                spiciness="순함",
                primary_texture="부드러움",
            ),
            make_item(
                "바삭 매운 치킨",
                texture="바삭함",
                spiciness="매움",
                primary_texture="바삭함",
                cooking_method="fried",
            ),
        ]

        ranked = rerank_menu_items("맥주랑 어울리는 치킨 추천해줘", items)

        self.assertEqual(ranked[0]["name"], "바삭 매운 치킨")
        self.assertIn("recommendation_reason", ranked[0])
        self.assertEqual(ranked[0]["matched_criteria"], "beer_pairing")
        self.assertNotIn("main_chicken", ranked[0]["recommendation_reason"])

    def test_kids_friendly_penalizes_spicy_items(self):
        from tools.recommendation_criteria import rerank_menu_items

        items = [
            make_item("매운 치킨", texture="바삭함", spiciness="매움"),
            make_item(
                "순한 치킨",
                texture="부드러움",
                spiciness="순함",
                primary_texture="부드러움",
            ),
        ]

        ranked = rerank_menu_items("아이랑 먹기 좋은 치킨 추천해줘", items)

        self.assertEqual(ranked[0]["name"], "순한 치킨")

    def test_solo_meal_favors_single_chicken_items(self):
        from tools.recommendation_criteria import rerank_menu_items

        items = [
            make_item("큰 세트", category="세트메뉴", product_type="set_menu"),
            make_item("1인 치킨", category="1인분 메뉴", option_tags="반마리"),
        ]

        ranked = rerank_menu_items("혼자 먹을 메뉴 추천해줘", items)

        self.assertEqual(ranked[0]["name"], "1인 치킨")

    def test_non_criteria_query_returns_items_unchanged(self):
        from tools.recommendation_criteria import rerank_menu_items

        items = [
            make_item("첫 번째 치킨", texture="바삭함"),
            make_item("두 번째 치킨", texture="부드러움"),
        ]

        ranked = rerank_menu_items("바삭한 치킨 추천해줘", items)

        self.assertEqual([item["name"] for item in ranked], ["첫 번째 치킨", "두 번째 치킨"])
        self.assertNotIn("recommendation_reason", ranked[0])


class SearchMenuCriteriaIntegrationTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("tools.search_menu.build_redis_cache", return_value=None)
        self.addCleanup(patcher.stop)
        patcher.start()

    @patch("tools.search_menu._get_retriever")
    def test_search_menu_bypasses_stale_cache_for_criteria_query(
        self, mock_get_retriever
    ):
        from tools.search_menu import search_menu

        mock_get_retriever.return_value.invoke.return_value = [
            make_doc(
                "바삭 매운 치킨",
                texture="바삭함",
                spiciness="매움",
                primary_texture="바삭함",
                cooking_method="fried",
            ),
        ]

        payload = json.loads(
            search_menu.func(
                "치맥하려고 하는데 이에 맞는 치킨을 추천해줘",
                {
                    "menu_results": {
                        "치맥하려고 하는데 이에 맞는 치킨을 추천해줘": [
                            make_item("이전 캐시 메뉴", texture="부드러움", spiciness="순함")
                        ]
                    }
                },
            )
        )

        self.assertEqual(payload["results"][0]["name"], "바삭 매운 치킨")
        mock_get_retriever.return_value.invoke.assert_called_once()

    @patch("tools.search_menu._get_retriever")
    def test_search_menu_uses_criteria_retrieval_query_for_abstract_request(
        self, mock_get_retriever
    ):
        from tools.search_menu import search_menu

        mock_get_retriever.return_value.invoke.return_value = [
            make_doc(
                "바삭 매운 치킨",
                texture="바삭함",
                spiciness="매움",
                primary_texture="바삭함",
                cooking_method="fried",
            ),
        ]

        search_menu.func("치맥하려고 하는데 이에 맞는 치킨을 추천해줘", {"menu_results": {}})

        invoked_query = mock_get_retriever.return_value.invoke.call_args.args[0]
        self.assertEqual(invoked_query, "바삭한 매운 치킨")

    @patch("tools.search_menu._get_retriever")
    def test_search_menu_expands_candidate_pool_for_criteria_query(
        self, mock_get_retriever
    ):
        from tools.search_menu import search_menu

        retriever = mock_get_retriever.return_value
        retriever.search_kwargs = {"k": 5}
        observed_k = []

        def invoke(_query):
            observed_k.append(retriever.search_kwargs["k"])
            return [
                make_doc(
                    "바삭 매운 치킨",
                    texture="바삭함",
                    spiciness="매움",
                    primary_texture="바삭함",
                    cooking_method="fried",
                )
            ]

        retriever.invoke.side_effect = invoke

        search_menu.func("치맥하려고 하는데 이에 맞는 치킨을 추천해줘", {"menu_results": {}})

        self.assertEqual(observed_k, [12])
        self.assertEqual(retriever.search_kwargs["k"], 5)

    @patch("tools.search_menu._get_retriever")
    def test_search_menu_adds_recommendation_fields_for_criteria_query(
        self, mock_get_retriever
    ):
        from tools.search_menu import search_menu

        mock_get_retriever.return_value.invoke.return_value = [
            make_doc(
                "순한 부드러운 치킨",
                texture="부드러움",
                spiciness="순함",
                primary_texture="부드러움",
            ),
            make_doc(
                "바삭 매운 치킨",
                texture="바삭함",
                spiciness="매움",
                primary_texture="바삭함",
                cooking_method="fried",
            ),
        ]

        payload = json.loads(search_menu.func("맥주랑 어울리는 치킨 추천해줘", {"menu_results": {}}))

        self.assertEqual(payload["results"][0]["name"], "바삭 매운 치킨")
        self.assertEqual(payload["results"][0]["matched_criteria"], "beer_pairing")
        self.assertTrue(payload["results"][0]["recommendation_reason"])

    def test_format_menu_cards_preserves_recommendation_fields(self):
        from tools.final_answer import format_menu_cards

        payload = format_menu_cards(
            [
                {
                    "name": "바삭 매운 치킨",
                    "category": "후라이드",
                    "price": 23000,
                    "description": "설명",
                    "recommendation_reason": "추천 기준상 잘 맞습니다.",
                    "recommendation_score": 5,
                    "matched_criteria": "beer_pairing",
                }
            ]
        )

        card = payload["items"][0]
        self.assertEqual(card["recommendation_reason"], "추천 기준상 잘 맞습니다.")
        self.assertEqual(card["recommendation_score"], 5)
        self.assertEqual(card["matched_criteria"], "beer_pairing")

    @patch("tools.search_menu._get_retriever")
    def test_kids_friendly_search_excludes_sauce_and_drink_candidates(
        self, mock_get_retriever
    ):
        from tools.search_menu import search_menu

        mock_get_retriever.return_value.invoke.return_value = [
            make_doc(
                "BBQ양념치킨컵소스(40g)",
                product_type="sauce",
                product_family="sauce",
            ),
            make_doc(
                "콜라500ml",
                product_type="drink",
                product_family="drink",
            ),
            make_doc(
                "황금올리브치킨™속안심",
                texture="부드러움",
                spiciness="순함",
                primary_texture="부드러움",
                option_tags="순살",
            ),
        ]

        payload = json.loads(
            search_menu.func("아이가 먹을 수 있는 메뉴 추천해줘", {"menu_results": {}})
        )

        self.assertEqual(
            [item["name"] for item in payload["results"]],
            ["황금올리브치킨™속안심"],
        )

    @patch("tools.search_menu._get_retriever")
    def test_generic_menu_recommendation_excludes_sauce_by_default(
        self, mock_get_retriever
    ):
        from tools.search_menu import search_menu

        retriever = mock_get_retriever.return_value
        retriever.vectorstore.similarity_search.return_value = [
            make_doc("BBQ 소스", product_type="sauce", product_family="sauce"),
            make_doc("황금올리브치킨™", texture="바삭함", spiciness="순함"),
        ]

        payload = json.loads(search_menu.func("맛있는 메뉴 추천해줘", {"menu_results": {}}))

        self.assertEqual(
            [item["name"] for item in payload["results"]],
            ["황금올리브치킨™"],
        )


if __name__ == "__main__":
    unittest.main()
