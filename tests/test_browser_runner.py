import io
import os
import sys
import types
import unittest
from unittest.mock import patch


class FakeTools:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def action(self, description, **kwargs):
        def decorator(func):
            return func

        return decorator


class FakeActionResult:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class BrowserRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_browser_task_keeps_browser_alive_for_manual_resume(self) -> None:
        from browser import run_browser_task

        created_sessions = []
        created_agents = []

        class FakeBrowserSession:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.stopped = False
                created_sessions.append(self)

            async def stop(self):
                self.stopped = True
                return None

        class FakeHistory:
            def is_done(self):
                return True

            def final_result(self):
                return "ready"

            def urls(self):
                return ["https://www.bbq.co.kr/order/cart"]

        class FakeAgent:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                created_agents.append(self)

            async def run(self, max_steps):
                return FakeHistory()

        fake_browser_use = types.SimpleNamespace(
            ActionResult=FakeActionResult,
            Agent=FakeAgent,
            BrowserSession=FakeBrowserSession,
            ChatOpenAI=lambda model: object(),
            Tools=FakeTools,
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch.dict(
            sys.modules, {"browser_use": fake_browser_use}
        ):
            result = await run_browser_task.run_browser_task(
                task="open bbq",
                model="gpt-test",
                max_steps=1,
                headless=False,
                resume_task="continue order",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(created_sessions[0].kwargs["keep_alive"], True)
        self.assertTrue(created_agents[0].kwargs["use_vision"])

    async def test_run_browser_task_can_keep_headed_browser_open_and_returns_url(self) -> None:
        from browser import run_browser_task

        created_sessions = []

        class FakeBrowserSession:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.stopped = False
                created_sessions.append(self)

            async def stop(self):
                self.stopped = True
                return None

        class FakeHistory:
            def is_done(self):
                return True

            def final_result(self):
                return "cart ready"

            def urls(self):
                return [None, "https://www.bbq.co.kr/order/cart"]

        class FakeAgent:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            async def run(self, max_steps):
                return FakeHistory()

        fake_browser_use = types.SimpleNamespace(
            ActionResult=FakeActionResult,
            Agent=FakeAgent,
            BrowserSession=FakeBrowserSession,
            ChatOpenAI=lambda model: object(),
            Tools=FakeTools,
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch.dict(
            sys.modules, {"browser_use": fake_browser_use}
        ):
            result = await run_browser_task.run_browser_task(
                task="open bbq",
                model="gpt-test",
                max_steps=1,
                headless=False,
                keep_open_on_completion=True,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["current_url"], "https://www.bbq.co.kr/order/cart")
        self.assertFalse(created_sessions[0].stopped)

    async def test_manual_checkpoint_prompt_does_not_write_to_stdout(self) -> None:
        from browser import run_browser_task

        class FakeBrowserSession:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            async def stop(self):
                return None

        class FakeHistory:
            def is_done(self):
                return True

            def final_result(self):
                return "ready"

            def urls(self):
                return []

        class FakeAgent:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            async def run(self, max_steps):
                return FakeHistory()

        fake_browser_use = types.SimpleNamespace(
            ActionResult=FakeActionResult,
            Agent=FakeAgent,
            BrowserSession=FakeBrowserSession,
            ChatOpenAI=lambda model: object(),
            Tools=FakeTools,
        )

        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch.dict(
            sys.modules, {"browser_use": fake_browser_use}
        ), patch("builtins.input", return_value="") as mock_input, patch(
            "sys.stdout", stdout
        ), patch("sys.stderr", stderr):
            result = await run_browser_task.run_browser_task(
                task="open bbq",
                model="gpt-test",
                max_steps=1,
                headless=False,
                resume_task="continue order",
                manual_checkpoint="Complete login in the browser.",
            )

        self.assertTrue(result["ok"])
        mock_input.assert_called_once_with()
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Complete login in the browser.", stderr.getvalue())

    async def test_run_browser_task_registers_custom_order_click_tools(self) -> None:
        from browser import run_browser_task

        created_agents = []
        registered_actions = []

        class FakeBrowserSession:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            async def stop(self):
                return None

        class FakeTools:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def action(self, description, **kwargs):
                registered_actions.append((description, kwargs))

                def decorator(func):
                    return func

                return decorator

        class FakeActionResult:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeHistory:
            def is_done(self):
                return True

            def final_result(self):
                return "ready"

            def urls(self):
                return []

        class FakeAgent:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                created_agents.append(self)

            async def run(self, max_steps):
                return FakeHistory()

        fake_browser_use = types.SimpleNamespace(
            ActionResult=FakeActionResult,
            Agent=FakeAgent,
            BrowserSession=FakeBrowserSession,
            ChatOpenAI=lambda model: object(),
            Tools=FakeTools,
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch.dict(
            sys.modules, {"browser_use": fake_browser_use}
        ):
            result = await run_browser_task.run_browser_task(
                task="open bbq",
                model="gpt-test",
                max_steps=1,
                headless=False,
                resume_task="continue order",
            )

        self.assertTrue(result["ok"])
        self.assertIs(created_agents[0].kwargs["tools"], created_agents[1].kwargs["tools"])
        descriptions = [description for description, _kwargs in registered_actions]
        self.assertIn("Click the exact BBQ menu item by full visible name", descriptions)
        self.assertIn("Click an exact BBQ option within its option group", descriptions)
        self.assertIn(
            "Click BBQ add-to-cart only after selected options are visible",
            descriptions,
        )
        self.assertIn("Click BBQ move-to-cart only after add-to-cart", descriptions)

    async def test_add_to_cart_tool_does_not_click_same_cart_button_twice(self) -> None:
        from browser import run_browser_task

        registered_actions = {}

        class CapturingTools:
            def action(self, description, **kwargs):
                def decorator(func):
                    registered_actions[description] = func
                    return func

                return decorator

        class FakeElement:
            def __init__(self, page):
                self.page = page

            async def click(self):
                self.page.click_count += 1

        class FakePage:
            def __init__(self):
                self.click_count = 0

            async def evaluate(self, _script):
                return "마라핫 콜라 1.25L"

            async def must_get_element_by_prompt(self, _prompt, llm):
                return FakeElement(self)

        class FakeBrowserSession:
            def __init__(self, page):
                self.page = page

            async def get_current_page(self):
                return self.page

        class FakeActionResult:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        run_browser_task._build_bbq_order_tools(
            CapturingTools,
            FakeActionResult,
            FakeBrowserSession,
            object(),
        )

        add_to_cart = registered_actions[
            "Click BBQ add-to-cart only after selected options are visible"
        ]
        page = FakePage()
        session = FakeBrowserSession(page)

        first_result = await add_to_cart(["콜라 1.25L"], "장바구니 담기", session)
        second_result = await add_to_cart(["콜라 1.25L"], "장바구니 담기", session)

        self.assertEqual(page.click_count, 1)
        self.assertIn("Already clicked", second_result.kwargs["extracted_content"])
        self.assertNotIn("Already clicked", first_result.kwargs["extracted_content"])


if __name__ == "__main__":
    unittest.main()
