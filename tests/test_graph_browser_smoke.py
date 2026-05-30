import unittest
from unittest.mock import AsyncMock, patch


class TestGraphOrderSmoke(unittest.IsolatedAsyncioTestCase):
    async def test_run_order_smoke_uses_order_prompt(self) -> None:
        import test_graph

        with patch.object(test_graph, "run", new=AsyncMock()) as mock_run:
            mock_run.return_value = (
                {"type": "text", "message": "Example Domain"},
                [],
                {"menu_results": {}, "cs_results": {}},
            )

            response = await test_graph.run_order_smoke()

        self.assertEqual(response["message"], "Example Domain")
        user_input = mock_run.call_args.args[0]
        self.assertIn("황금올리브", user_input)
        self.assertIn("장바구니", user_input)


if __name__ == "__main__":
    unittest.main()
