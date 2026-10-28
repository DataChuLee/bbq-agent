import unittest


class FakePage:
    def __init__(self, visible_text: str):
        self.visible_text = visible_text
        self.clicks = []
        self.urls = []
        self.url = "https://www.bbq.co.kr/order/cart"

    async def goto(self, url):
        self.urls.append(url)

    async def evaluate(self, _script):
        return self.visible_text

    async def click_exact_text(self, text):
        if text not in self.visible_text:
            return False
        self.clicks.append(text)
        return True


class FakeBrowserSession:
    def __init__(self, page):
        self.page = page

    async def get_current_page(self):
        return self.page

    async def get_current_page_url(self):
        return self.page.url


class DomOnlyFalsePage:
    url = "https://www.bbq.co.kr"

    def __init__(self):
        self.urls = []
        self.dom_click_scripts = []

    async def goto(self, url):
        self.urls.append(url)

    async def evaluate(self, script, *args):
        if args:
            self.dom_click_scripts.append(script)
            return "false"
        return "배달\n메뉴\nFried\nGolden Olive Chicken"


class GroupedOptionPage(FakePage):
    async def click_exact_text(self, text):
        if text == "Coke 1.25L":
            return False
        return await super().click_exact_text(text)

    async def click_exact_option(self, option_name, group_name):
        if group_name != "Drink selection" or option_name != "Coke 1.25L":
            return False
        self.clicks.append(f"{group_name} -> {option_name}")
        return True


class DeterministicOrderTests(unittest.IsolatedAsyncioTestCase):
    async def test_deterministic_order_clicks_exact_route_and_reports_cart_ready(
        self,
    ) -> None:
        from browser.bbq_deterministic_order import BBQ_URL, run_deterministic_order

        page = FakePage(
            "\n".join(
                [
                    "배달",
                    "메뉴",
                    "Fried",
                    "Golden Olive Chicken",
                    "Coke 1.25L",
                    "장바구니 담기",
                    "장바구니로 이동하기",
                ]
            )
        )

        result = await run_deterministic_order(
            browser_session=FakeBrowserSession(page),
            order={
                "menu_name": "Golden Olive Chicken",
                "menu_category": "Fried",
                "options": ["Coke 1.25L"],
                "order_type": "delivery",
                "option_details": [],
            },
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["done"])
        self.assertEqual(result["result"], "Cart is ready")
        self.assertEqual(result["current_url"], "https://www.bbq.co.kr/order/cart")
        self.assertEqual(page.urls, [BBQ_URL])
        self.assertEqual(
            page.clicks,
            [
                "배달",
                "메뉴",
                "Fried",
                "Golden Olive Chicken",
                "Coke 1.25L",
                "배달",
                "장바구니 담기",
                "장바구니로 이동하기",
            ],
        )

    async def test_deterministic_order_reports_missing_option_without_cart_click(
        self,
    ) -> None:
        from browser.bbq_deterministic_order import run_deterministic_order

        page = FakePage(
            "\n".join(
                [
                    "배달",
                    "메뉴",
                    "Fried",
                    "Golden Olive Chicken",
                    "장바구니 담기",
                ]
            )
        )

        result = await run_deterministic_order(
            browser_session=FakeBrowserSession(page),
            order={
                "menu_name": "Golden Olive Chicken",
                "menu_category": "Fried",
                "options": ["Coke 1.25L"],
                "order_type": "delivery",
                "option_details": [],
            },
        )

        self.assertTrue(result["ok"])
        self.assertFalse(result["done"])
        self.assertEqual(result["result"], "Selected options are missing")
        self.assertEqual(result["missing_options"], ["Coke 1.25L"])
        self.assertNotIn("장바구니 담기", page.clicks)

    async def test_browser_use_string_false_dom_click_is_not_success(self) -> None:
        from browser.bbq_deterministic_order import (
            DeterministicNavigationError,
            run_deterministic_order,
        )

        page = DomOnlyFalsePage()

        with self.assertRaises(DeterministicNavigationError):
            await run_deterministic_order(
                browser_session=FakeBrowserSession(page),
                order={
                    "menu_name": "Golden Olive Chicken",
                    "menu_category": "Fried",
                    "options": [],
                    "order_type": "delivery",
                    "option_details": [],
                },
            )

        self.assertTrue(page.dom_click_scripts)
        self.assertTrue(page.dom_click_scripts[0].startswith("("))

    async def test_option_details_use_group_scoped_option_click(self) -> None:
        from browser.bbq_deterministic_order import run_deterministic_order

        page = GroupedOptionPage(
            "\n".join(
                [
                    "배달",
                    "메뉴",
                    "Fried",
                    "Golden Olive Chicken",
                    "Drink selection",
                    "Coke 1.25L",
                    "장바구니 담기",
                ]
            )
        )

        result = await run_deterministic_order(
            browser_session=FakeBrowserSession(page),
            order={
                "menu_name": "Golden Olive Chicken",
                "menu_category": "Fried",
                "options": ["Coke 1.25L"],
                "order_type": "delivery",
                "option_details": [
                    {
                        "group_name": "Drink selection",
                        "option_name": "Coke 1.25L",
                        "required": True,
                    }
                ],
            },
        )

        self.assertTrue(result["ok"])
        self.assertIn("Drink selection -> Coke 1.25L", page.clicks)


if __name__ == "__main__":
    unittest.main()
